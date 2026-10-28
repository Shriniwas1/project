"""Phase 5: Forecast Accuracy Calculation Service.

Computes MAE, RMSE, Bias, and MAPE from matched forecast vs. actual comparison rows
over a requested date range, using the strict day-ahead vintage selection engine.

Metric definitions (all operate on 30-minute half-hourly matched rows):

    error_mw = forecast_generation_mw - actual_generation_mw

    MAE  = mean(|error|)                                [units: MW]
    RMSE = sqrt(mean(error²))                           [units: MW]
    Bias = mean(error)                                  [units: MW]
    MAPE = mean(|error| / |actual|) × 100               [units: %]

MAPE exclusion rule:
    Intervals where actual_generation_mw == 0 are excluded from MAPE only.
    They are still included in MAE, RMSE, and Bias (error is well-defined).
    MAPE returns None when no eligible observations remain.

Resolution bridge (Phase 4 design, preserved here):
    FUELHH actuals: 30-minute resolution (48 intervals/day).
    WINDFOR forecasts: 1-hour resolution (24 intervals/day).
    Each 30-minute actual (HH:00 and HH:30) is matched to the enclosing
    1-hour forecast interval (HH:00). The same forecast row may therefore
    produce TWO matched half-hourly comparison rows per hour.
    Metric denominators use the count of matched 30-minute rows, not
    the count of unique hourly forecasts. This is intentional and documented.

Look-ahead bias guarantee (inherited from Phase 4):
    Only forecasts published AT OR BEFORE the D-1 decision cutoff are used.
    No future forecast is ever mixed into historical evaluation.
"""

import logging
import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.timezone import (
    calculate_decision_cutoff,
    format_utc_iso,
)
from backend.app.schemas.analytics import AccuracyMetricsSchema
from backend.app.schemas.comparison import ComparisonIntervalSchema
from backend.app.services.forecast_selection_service import ForecastSelectionService

logger = logging.getLogger(__name__)


def _compute_metrics(
    matched_rows: List[ComparisonIntervalSchema],
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], int, int]:
    """Compute MAE, RMSE, Bias, MAPE from a list of matched ComparisonIntervalSchema rows.

    Args:
        matched_rows: Pre-filtered list where is_matched == True.

    Returns:
        (mae_mw, rmse_mw, bias_mw, mape_pct, zero_actual_count, mape_eligible_count)

    Notes:
        - matched_rows must only contain rows where is_matched is True.
        - forecast_error_mw is expected to be set (not None) for all matched rows.
        - MAPE excludes rows where actual_generation_mw == 0.
        - All four metrics are None when matched_rows is empty.
    """
    n = len(matched_rows)
    if n == 0:
        return None, None, None, None, 0, 0

    errors: List[float] = []
    for row in matched_rows:
        # forecast_error_mw is guaranteed non-None for matched rows by the selection service
        err = row.forecast_error_mw
        if err is None:
            # Defensive: skip rows that are structurally matched but have no error (shouldn't happen)
            logger.warning(
                "Matched row at %s has forecast_error_mw=None; skipping from metrics.",
                row.delivery_timestamp,
            )
            continue
        errors.append(err)

    n_valid = len(errors)
    if n_valid == 0:
        return None, None, None, None, 0, 0

    mae_mw = sum(abs(e) for e in errors) / n_valid
    rmse_mw = math.sqrt(sum(e ** 2 for e in errors) / n_valid)
    bias_mw = sum(errors) / n_valid

    # MAPE: exclude rows where actual == 0
    mape_errors: List[float] = []
    zero_actual_count = 0
    for row in matched_rows:
        if row.forecast_error_mw is None:
            continue
        actual = row.actual_generation_mw
        if actual is None or actual == 0.0:
            zero_actual_count += 1
            continue
        mape_errors.append(abs(row.forecast_error_mw) / abs(actual))

    mape_eligible_count = len(mape_errors)
    mape_pct: Optional[float] = None
    if mape_eligible_count > 0:
        mape_pct = (sum(mape_errors) / mape_eligible_count) * 100.0

    return mae_mw, rmse_mw, bias_mw, mape_pct, zero_actual_count, mape_eligible_count


class AccuracyService:
    """Calculates forecast accuracy metrics over a date range using Phase 4 comparison engine."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._selection_svc = ForecastSelectionService(db=db)

    async def compute_accuracy(
        self,
        date_from: date,
        date_to: date,
        cutoff_time_str: str = "11:00",
    ) -> AccuracyMetricsSchema:
        """Compute accuracy metrics for all matched intervals in [date_from, date_to] inclusive.

        Algorithm:
        1. Iterate each delivery date in the range (inclusive on both ends).
        2. For each date call build_comparison_for_date (Phase 4 selection engine).
        3. Collect all matched ComparisonIntervalSchema rows across the range.
        4. Compute MAE, RMSE, Bias, MAPE from matched rows.
        5. Return AccuracyMetricsSchema with full coverage audit.

        The cutoff is applied per-date (D-1 at cutoff_time_str Europe/London).
        Coverage counts are half-hourly throughout (never conflated with hourly).

        Args:
            date_from: First delivery date (inclusive).
            date_to:   Last delivery date (inclusive).
            cutoff_time_str: Decision cutoff in HH:MM Europe/London (default "11:00").

        Returns:
            AccuracyMetricsSchema with metrics and coverage counts.
        """
        if date_from > date_to:
            raise ValueError(
                f"date_from ({date_from}) must be <= date_to ({date_to})."
            )

        # Reference cutoff UTC relative to the first date's D-1 (kept for single-date requests / backward compatibility)
        reference_cutoff_utc = calculate_decision_cutoff(date_from, cutoff_time_str)

        decision_cutoffs_by_date: Dict[str, str] = {}
        total_expected_intervals = 0
        total_actual_available = 0
        total_forecast_available = 0
        all_selected_forecast_keys = set()
        all_matched_rows: List[ComparisonIntervalSchema] = []

        current_date = date_from
        while current_date <= date_to:
            day_cutoff_utc = calculate_decision_cutoff(current_date, cutoff_time_str)
            decision_cutoffs_by_date[str(current_date)] = format_utc_iso(day_cutoff_utc)

            summary = await self._selection_svc.build_comparison_for_date(
                current_date, cutoff_time_str
            )

            total_expected_intervals += summary.total_intervals
            total_actual_available += (
                summary.total_intervals - summary.missing_actual_intervals
            )
            total_forecast_available += (
                summary.total_intervals - summary.missing_forecast_intervals
            )

            for row in summary.intervals:
                if row.is_forecast_available and row.forecast_publish_timestamp:
                    # Floor delivery timestamp to 1-hour boundary to identify unique hourly forecast
                    hour_ts = row.delivery_timestamp[:13] + ":00:00Z"
                    all_selected_forecast_keys.add((hour_ts, row.forecast_publish_timestamp))
                if row.is_matched:
                    all_matched_rows.append(row)

            current_date += timedelta(days=1)

        matched_count = len(all_matched_rows)
        mae_mw, rmse_mw, bias_mw, mape_pct, zero_actual_count, mape_eligible_count = (
            _compute_metrics(all_matched_rows)
        )

        # Round metrics to 4 decimal places for clean API output
        return AccuracyMetricsSchema(
            date_range_start=str(date_from),
            date_range_end=str(date_to),
            date_boundary_type="inclusive",
            cutoff_time_local=cutoff_time_str,
            cutoff_timezone="Europe/London",
            cutoff_rule=f"D-1 at {cutoff_time_str} Europe/London applied separately to each delivery date",
            cutoff_applied_per_delivery_date=True,
            decision_cutoff_utc=format_utc_iso(reference_cutoff_utc),
            decision_cutoffs_by_date=decision_cutoffs_by_date,
            actual_resolution="30-minute settlement periods",
            forecast_resolution="1-hour intervals (WINDFOR)",
            expected_interval_count=total_expected_intervals,
            actual_interval_count=total_actual_available,
            unique_actual_records_count=total_actual_available,
            unique_hourly_forecast_count=len(all_selected_forecast_keys),
            forecast_covered_interval_count=total_forecast_available,
            forecast_interval_count=total_forecast_available,
            matched_interval_count=matched_count,
            zero_actual_excluded_count=zero_actual_count,
            mape_eligible_count=mape_eligible_count,
            mae_mw=round(mae_mw, 4) if mae_mw is not None else None,
            rmse_mw=round(rmse_mw, 4) if rmse_mw is not None else None,
            bias_mw=round(bias_mw, 4) if bias_mw is not None else None,
            mape_pct=round(mape_pct, 4) if mape_pct is not None else None,
            mae_unit="MW",
            rmse_unit="MW",
            bias_unit="MW",
            mape_unit="%",
        )
