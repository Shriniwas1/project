"""Pydantic schemas for Phase 5 forecast accuracy metrics and analytics API.

Design principles:
- All metric counts are explicit: matched, excluded (zero-actual), missing.
- MAPE is None when no eligible observations exist; never coerced to 0.
- Units are documented on every numeric metric field.
- The half-hourly vs. hourly resolution distinction is reported in the schema.
- Coverage fields must not claim full coverage unless verified.
"""

from datetime import date
from typing import Dict, Optional
from pydantic import BaseModel, Field


class AccuracyMetricsSchema(BaseModel):
    """Computed forecast accuracy metrics for a date range at a given decision cutoff.

    All metrics are computed from matched 30-minute half-hourly comparison rows.
    One hourly WINDFOR forecast may be used to match two half-hourly actual intervals.
    This is by design (resolution bridge) and is reflected in matched_interval_count.

    Error sign convention:
        forecast_error = forecast_generation_mw - actual_generation_mw
        Positive error  → overforecast (forecast exceeds actual).
        Negative error  → underforecast (forecast below actual).
    """

    # -----------------------------------------------------------------------
    # Request context & date boundary metadata
    # -----------------------------------------------------------------------
    date_range_start: str = Field(
        ...,
        description="First delivery date in the requested range (Europe/London, inclusive)."
    )
    date_range_end: str = Field(
        ...,
        description="Last delivery date in the requested range (Europe/London, inclusive)."
    )
    date_boundary_type: str = Field(
        "inclusive",
        description="Date boundary specification: both date_range_start and date_range_end are inclusive."
    )
    cutoff_time_local: str = Field(
        ...,
        description="Decision cutoff time in Europe/London (HH:MM). Default: '11:00'."
    )
    cutoff_timezone: str = Field(
        "Europe/London",
        description="Timezone in which cutoff_time_local is specified and evaluated."
    )
    cutoff_rule: str = Field(
        ...,
        description="Human-readable cutoff rule (e.g. 'D-1 at 11:00 Europe/London applied separately to each delivery date')."
    )
    cutoff_applied_per_delivery_date: bool = Field(
        True,
        description="True: decision cutoff is evaluated per delivery date (D-1 at cutoff_time_local)."
    )
    decision_cutoff_utc: str = Field(
        ...,
        description=(
            "Reference D-1 decision cutoff UTC timestamp for date_range_start. "
            "For date-specific cutoffs across a multi-day range, see decision_cutoffs_by_date."
        )
    )
    decision_cutoffs_by_date: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-delivery-date map of D-1 decision cutoff timestamps in UTC ISO-8601."
    )

    # -----------------------------------------------------------------------
    # Resolution information
    # -----------------------------------------------------------------------
    actual_resolution: str = Field(
        "30-minute settlement periods",
        description="Native resolution of FUELHH actual generation data."
    )
    forecast_resolution: str = Field(
        "1-hour intervals (WINDFOR)",
        description=(
            "Native resolution of WINDFOR forecast data. Each 1-hour forecast is "
            "matched to the two 30-minute actual intervals within that hour."
        )
    )

    # -----------------------------------------------------------------------
    # Coverage counts (distinguishing half-hourly intervals vs. unique hourly forecasts)
    # -----------------------------------------------------------------------
    expected_interval_count: int = Field(
        ...,
        description=(
            "Total expected 30-minute delivery intervals for the date range "
            "(days × 48). Not all may have data."
        )
    )
    actual_interval_count: int = Field(
        ...,
        description=(
            "Half-hourly intervals with actual outturn available in the database. "
            "Each 30-minute settlement period contributes at most once."
        )
    )
    unique_actual_records_count: int = Field(
        ...,
        description="Unique 30-minute FUELHH actual generation records present in the database."
    )
    unique_hourly_forecast_count: int = Field(
        ...,
        description=(
            "Number of distinct hourly WINDFOR forecast records selected across the date range. "
            "At most 24 unique forecasts per day."
        )
    )
    forecast_covered_interval_count: int = Field(
        ...,
        description=(
            "Half-hourly settlement intervals covered by an eligible day-ahead hourly forecast "
            "(published ≤ decision cutoff). Up to 48 intervals per day."
        )
    )
    forecast_interval_count: int = Field(
        ...,
        description=(
            "Alias for forecast_covered_interval_count (half-hourly intervals covered by an eligible forecast). "
            "Preserved for backward compatibility."
        )
    )
    matched_interval_count: int = Field(
        ...,
        description=(
            "Half-hourly intervals where both actual and forecast are available. "
            "These are the only intervals used for metric calculations. "
            "Note: two 30-minute rows may share the same 1-hour WINDFOR forecast "
            "— they are still counted as two independent half-hourly comparison rows."
        )
    )
    zero_actual_excluded_count: int = Field(
        ...,
        description=(
            "Matched intervals where actual_generation_mw == 0, excluded from MAPE only. "
            "Still included in MAE, RMSE, and Bias."
        )
    )
    mape_eligible_count: int = Field(
        ...,
        description=(
            "Matched intervals used for MAPE calculation "
            "(matched_interval_count minus zero_actual_excluded_count)."
        )
    )

    # -----------------------------------------------------------------------
    # Accuracy metrics & units — all computed on matched half-hourly rows
    # -----------------------------------------------------------------------
    mae_mw: Optional[float] = Field(
        None,
        description=(
            "Mean Absolute Error in MW. "
            "mae = mean(|forecast - actual|) over matched intervals. "
            "None if matched_interval_count == 0."
        )
    )
    rmse_mw: Optional[float] = Field(
        None,
        description=(
            "Root Mean Squared Error in MW. "
            "rmse = sqrt(mean((forecast - actual)²)) over matched intervals. "
            "None if matched_interval_count == 0."
        )
    )
    bias_mw: Optional[float] = Field(
        None,
        description=(
            "Mean Forecast Bias in MW. "
            "bias = mean(forecast - actual) over matched intervals. "
            "Positive = systematic overforecast; negative = systematic underforecast. "
            "None if matched_interval_count == 0."
        )
    )
    mape_pct: Optional[float] = Field(
        None,
        description=(
            "Mean Absolute Percentage Error in %. "
            "mape = mean(|forecast - actual| / |actual|) × 100 over MAPE-eligible intervals. "
            "Zero-actual intervals are excluded; division by zero is never performed. "
            "None if mape_eligible_count == 0."
        )
    )
    mae_unit: str = Field("MW", description="Unit of measurement for MAE.")
    rmse_unit: str = Field("MW", description="Unit of measurement for RMSE.")
    bias_unit: str = Field("MW", description="Unit of measurement for Bias.")
    mape_unit: str = Field("%", description="Unit of measurement for MAPE.")

