"""Forecast Selection Service: Day-Ahead Vintage Selection Engine.

Business Logic:
    For a given delivery date D and a configurable decision cutoff time:
    1. Decision date = D - 1.
    2. Decision cutoff = D-1 at cutoff_time in Europe/London, converted to UTC.
    3. For each 30-minute actual generation interval on D:
       a. Find all WINDFOR forecasts with delivery_timestamp within the
          corresponding 1-hour WINDFOR interval.
       b. Filter to forecasts with publish_timestamp <= decision_cutoff_utc.
       c. Select the LATEST eligible forecast (maximum publish_timestamp).
       d. If no eligible forecast exists, mark interval as unavailable.
    4. Never use forecasts published after the decision cutoff.
    5. Preserve the selected vintage's publish_timestamp.

Key invariant:
    No look-ahead bias. The selected forecast must have been genuinely available
    at the day-ahead decision time.

Resolution alignment:
    Actuals are 30-minute (FUELHH). Forecasts are 1-hour (WINDFOR).
    Each 30-min actual is matched to the forecast for its enclosing 1-hour interval:
      e.g. actuals at 12:00 and 12:30 both match the forecast with delivery_timestamp=12:00.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Dict, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.timezone import (
    UTC_TZ,
    ensure_utc,
    format_utc_iso,
    get_delivery_date_for_interval,
    calculate_decision_cutoff,
    calculate_settlement_period,
    get_delivery_day_bounds_utc,
)
from backend.app.models.actual import ActualGeneration
from backend.app.models.forecast import ForecastGeneration
from backend.app.schemas.comparison import (
    SelectedForecastSchema,
    ForecastVintageSchema,
    ComparisonIntervalSchema,
    ComparisonSummarySchema,
    ComparisonResponseSchema,
)

logger = logging.getLogger(__name__)


def _floor_to_hour(dt: datetime) -> datetime:
    """Return the given datetime floored to the enclosing 1-hour boundary (minutes/secs zeroed)."""
    return dt.replace(minute=0, second=0, microsecond=0)


class ForecastSelectionService:
    """Implements strict day-ahead forecast vintage selection with look-ahead bias prevention."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def select_forecast_for_interval(
        self,
        delivery_timestamp_utc: datetime,
        decision_cutoff_utc: datetime,
    ) -> Optional[ForecastGeneration]:
        """Select the latest eligible forecast for a single delivery interval.

        Algorithm:
        1. Floor the delivery timestamp to the 1-hour WINDFOR interval boundary.
        2. Query forecasts with delivery_timestamp == 1-hour boundary AND
           publish_timestamp <= decision_cutoff_utc.
        3. Return the row with the maximum publish_timestamp.

        Returns None if no eligible forecast exists.
        """
        hour_boundary = _floor_to_hour(delivery_timestamp_utc)

        stmt = (
            select(ForecastGeneration)
            .where(
                and_(
                    ForecastGeneration.delivery_timestamp == hour_boundary,
                    ForecastGeneration.publish_timestamp <= decision_cutoff_utc,
                )
            )
            .order_by(ForecastGeneration.publish_timestamp.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_selected_forecasts_for_date(
        self,
        delivery_date: date,
        cutoff_time_str: str = "11:00",
    ) -> List[SelectedForecastSchema]:
        """Return the day-ahead selected forecast for every 30-min interval on delivery_date.

        Args:
            delivery_date: The GB business delivery date (Europe/London).
            cutoff_time_str: Decision cutoff in HH:MM Europe/London (default "11:00").

        Returns:
            List of SelectedForecastSchema, one per 30-min interval (up to 48).
            Intervals without an eligible forecast have is_forecast_available=False.
        """
        cutoff_utc = calculate_decision_cutoff(delivery_date, cutoff_time_str)
        start_utc, end_utc = get_delivery_day_bounds_utc(delivery_date)

        # Generate all expected 30-min delivery timestamps for this date
        intervals: List[datetime] = []
        ts = start_utc
        while ts < end_utc:
            intervals.append(ts)
            ts += timedelta(minutes=30)

        results = []
        for interval_utc in intervals:
            selected = await self.select_forecast_for_interval(interval_utc, cutoff_utc)
            sp = calculate_settlement_period(interval_utc)

            if selected is not None:
                pub_utc = ensure_utc(selected.publish_timestamp)
                lead_hours = (interval_utc - pub_utc).total_seconds() / 3600.0
                schema = SelectedForecastSchema(
                    delivery_timestamp=format_utc_iso(interval_utc),
                    delivery_date=str(delivery_date),
                    settlement_period=sp,
                    decision_cutoff_utc=format_utc_iso(cutoff_utc),
                    forecast_generation_mw=selected.generation_mw,
                    forecast_publish_timestamp=format_utc_iso(pub_utc),
                    forecast_lead_time_hours=round(lead_hours, 4),
                    is_forecast_available=True,
                )
            else:
                schema = SelectedForecastSchema(
                    delivery_timestamp=format_utc_iso(interval_utc),
                    delivery_date=str(delivery_date),
                    settlement_period=sp,
                    decision_cutoff_utc=format_utc_iso(cutoff_utc),
                    forecast_generation_mw=None,
                    forecast_publish_timestamp=None,
                    forecast_lead_time_hours=None,
                    is_forecast_available=False,
                )
            results.append(schema)

        return results

    async def get_forecast_vintages_for_date(
        self,
        delivery_date: date,
    ) -> List[ForecastVintageSchema]:
        """Return all stored forecast vintages for every 1-hour interval on delivery_date.

        Used by /api/forecast-vintages to show all available publication timestamps.
        """
        start_utc, end_utc = get_delivery_day_bounds_utc(delivery_date)

        stmt = (
            select(ForecastGeneration)
            .where(
                and_(
                    ForecastGeneration.delivery_timestamp >= start_utc,
                    ForecastGeneration.delivery_timestamp < end_utc,
                )
            )
            .order_by(
                ForecastGeneration.delivery_timestamp.asc(),
                ForecastGeneration.publish_timestamp.asc(),
            )
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        vintages = []
        for row in rows:
            deliv_utc = ensure_utc(row.delivery_timestamp)
            pub_utc = ensure_utc(row.publish_timestamp)
            lead_hours = (deliv_utc - pub_utc).total_seconds() / 3600.0
            vintages.append(
                ForecastVintageSchema(
                    delivery_timestamp=format_utc_iso(deliv_utc),
                    publish_timestamp=format_utc_iso(pub_utc),
                    generation_mw=row.generation_mw,
                    lead_time_hours=round(lead_hours, 4),
                    is_ex_ante=row.is_ex_ante,
                )
            )
        return vintages

    async def build_comparison_for_date(
        self,
        delivery_date: date,
        cutoff_time_str: str = "11:00",
    ) -> ComparisonSummarySchema:
        """Build a full forecast vs. actual comparison for every 30-min interval on delivery_date.

        Steps:
        1. Retrieve actual outturn records for delivery_date.
        2. For each actual interval, select the day-ahead forecast vintage.
        3. Calculate per-interval error where both are available.
        4. Return ComparisonSummarySchema with full interval list.

        Resolution bridge:
        - Actuals: 30-min intervals (SP 1–48).
        - Forecasts: 1-hour intervals. Each actual is matched to its enclosing 1-hour boundary.
        """
        cutoff_utc = calculate_decision_cutoff(delivery_date, cutoff_time_str)
        start_utc, end_utc = get_delivery_day_bounds_utc(delivery_date)

        # Fetch all actuals for this delivery date
        act_stmt = (
            select(ActualGeneration)
            .where(
                and_(
                    ActualGeneration.delivery_date == delivery_date,
                    ActualGeneration.source == "ELEXON_FUELHH",
                )
            )
            .order_by(ActualGeneration.delivery_timestamp.asc())
        )
        act_result = await self.db.execute(act_stmt)
        actual_rows = act_result.scalars().all()

        # Index actuals by UTC timestamp
        actual_map: Dict[datetime, ActualGeneration] = {}
        for row in actual_rows:
            ts = ensure_utc(row.delivery_timestamp)
            actual_map[ts] = row

        # Generate all expected 30-min intervals for this date
        intervals: List[datetime] = []
        ts = start_utc
        while ts < end_utc:
            intervals.append(ts)
            ts += timedelta(minutes=30)

        comparison_intervals: List[ComparisonIntervalSchema] = []
        matched_count = 0
        missing_actual_count = 0
        missing_forecast_count = 0
        selected_forecast_keys = set()

        for interval_utc in intervals:
            actual_row = actual_map.get(interval_utc)
            selected_fc = await self.select_forecast_for_interval(interval_utc, cutoff_utc)
            sp = calculate_settlement_period(interval_utc)

            # Actual
            actual_mw: Optional[float] = None
            is_actual_available = False
            if actual_row is not None:
                actual_mw = actual_row.generation_mw
                is_actual_available = True
            else:
                missing_actual_count += 1

            # Forecast
            forecast_mw: Optional[float] = None
            forecast_pub: Optional[str] = None
            is_forecast_available = False
            if selected_fc is not None:
                forecast_mw = selected_fc.generation_mw
                pub_utc = ensure_utc(selected_fc.publish_timestamp)
                deliv_hour_utc = ensure_utc(selected_fc.delivery_timestamp)
                forecast_pub = format_utc_iso(pub_utc)
                is_forecast_available = True
                selected_forecast_keys.add((deliv_hour_utc, pub_utc))
            else:
                missing_forecast_count += 1

            # Error metrics
            forecast_error: Optional[float] = None
            abs_error: Optional[float] = None
            pct_error: Optional[float] = None
            is_matched = is_actual_available and is_forecast_available

            if is_matched and actual_mw is not None and forecast_mw is not None:
                matched_count += 1
                forecast_error = round(forecast_mw - actual_mw, 4)
                abs_error = round(abs(forecast_error), 4)
                if actual_mw != 0.0:
                    pct_error = round(forecast_error / actual_mw * 100.0, 4)
                # pct_error stays None when actual == 0 (excluded from MAPE, not forced to zero)

            comparison_intervals.append(
                ComparisonIntervalSchema(
                    delivery_timestamp=format_utc_iso(interval_utc),
                    delivery_date=str(delivery_date),
                    settlement_period=sp,
                    decision_cutoff_utc=format_utc_iso(cutoff_utc),
                    actual_generation_mw=actual_mw,
                    is_actual_available=is_actual_available,
                    forecast_generation_mw=forecast_mw,
                    forecast_publish_timestamp=forecast_pub,
                    is_forecast_available=is_forecast_available,
                    forecast_error_mw=forecast_error,
                    absolute_error_mw=abs_error,
                    percentage_error=pct_error,
                    is_matched=is_matched,
                )
            )

        return ComparisonSummarySchema(
            delivery_date=str(delivery_date),
            decision_cutoff_utc=format_utc_iso(cutoff_utc),
            cutoff_time_local=cutoff_time_str,
            total_intervals=len(intervals),
            matched_intervals=matched_count,
            missing_actual_intervals=missing_actual_count,
            missing_forecast_intervals=missing_forecast_count,
            unique_hourly_forecasts=len(selected_forecast_keys),
            intervals=comparison_intervals,
        )

    async def build_comparison_for_date_range(
        self,
        date_from: date,
        date_to: date,
        cutoff_time_str: str = "11:00",
    ) -> ComparisonResponseSchema:
        """Build comparison across a date range [date_from, date_to] inclusive.

        Iterates each date in the range, applying the configured decision cutoff
        separately to each delivery date (D-1 at cutoff_time_str in Europe/London).

        Guarantees:
        - Strict vintage selection: only forecasts published <= date-specific D-1 cutoff.
        - Half-hourly comparison rows preserved.
        - Missing actuals or forecasts are never converted to zero.
        - Unique hourly forecasts selected vs. half-hourly covered intervals are distinguished.
        """
        if date_from > date_to:
            raise ValueError(f"date_from ({date_from}) must be <= date_to ({date_to}).")

        reference_cutoff_utc = calculate_decision_cutoff(date_from, cutoff_time_str)

        decision_cutoffs_by_date: Dict[str, str] = {}
        total_expected_intervals = 0
        total_actual_available = 0
        total_forecast_available = 0
        total_matched = 0
        total_missing_actuals = 0
        total_missing_forecasts = 0
        all_selected_forecast_keys = set()
        all_comparison_intervals: List[ComparisonIntervalSchema] = []

        current_date = date_from
        while current_date <= date_to:
            day_cutoff_utc = calculate_decision_cutoff(current_date, cutoff_time_str)
            decision_cutoffs_by_date[str(current_date)] = format_utc_iso(day_cutoff_utc)

            summary = await self.build_comparison_for_date(current_date, cutoff_time_str)

            total_expected_intervals += summary.total_intervals
            total_matched += summary.matched_intervals
            total_missing_actuals += summary.missing_actual_intervals
            total_missing_forecasts += summary.missing_forecast_intervals
            total_actual_available += (
                summary.total_intervals - summary.missing_actual_intervals
            )
            total_forecast_available += (
                summary.total_intervals - summary.missing_forecast_intervals
            )

            for row in summary.intervals:
                if row.is_forecast_available and row.forecast_publish_timestamp:
                    hour_ts = row.delivery_timestamp[:13] + ":00:00Z"
                    all_selected_forecast_keys.add((hour_ts, row.forecast_publish_timestamp))
                all_comparison_intervals.append(row)

            current_date += timedelta(days=1)

        return ComparisonResponseSchema(
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
            matched_interval_count=total_matched,
            missing_actual_intervals=total_missing_actuals,
            missing_forecast_intervals=total_missing_forecasts,
            intervals=all_comparison_intervals,
        )

