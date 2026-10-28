"""Pydantic schemas for forecast vintage selection and forecast vs. actual comparison.

These schemas represent the output of the day-ahead forecast selection engine (Phase 4).
They preserve full audit trails: which vintage was selected, what the cutoff was, and
whether the interval was matched, unmatched, or missing data.
"""

from datetime import date, datetime
from typing import Dict, Optional, List
from pydantic import BaseModel, Field


class SelectedForecastSchema(BaseModel):
    """A single delivery interval with the day-ahead selected forecast vintage.

    Represents the result of strict vintage selection:
    - The latest forecast published AT OR BEFORE the day-ahead decision cutoff.
    - publishTime is preserved for full audit trail.
    - If no eligible forecast exists, forecast fields are None and is_forecast_available=False.
    """

    delivery_timestamp: str = Field(
        ...,
        description="Delivery interval start time (UTC ISO-8601, e.g. '2026-01-01T12:00:00Z')"
    )
    delivery_date: str = Field(
        ...,
        description="Delivery date in Europe/London (e.g. '2026-01-01')"
    )
    settlement_period: Optional[int] = Field(
        None,
        description="GB settlement period number (1-48) for this delivery interval"
    )
    decision_cutoff_utc: str = Field(
        ...,
        description="Decision cutoff applied (UTC), i.e. D-1 at cutoff_time Europe/London"
    )

    # Selected forecast vintage
    forecast_generation_mw: Optional[float] = Field(
        None,
        description="Selected forecast wind generation in MW (None if no eligible forecast)"
    )
    forecast_publish_timestamp: Optional[str] = Field(
        None,
        description="Publish timestamp of the selected forecast vintage (UTC ISO-8601)"
    )
    forecast_lead_time_hours: Optional[float] = Field(
        None,
        description="Lead time from publication to delivery interval start, in hours"
    )
    is_forecast_available: bool = Field(
        ...,
        description="True if an eligible forecast was found at or before the decision cutoff"
    )


class ForecastVintageSchema(BaseModel):
    """A single available forecast publication for a delivery interval.

    Used by /api/forecast-vintages to return all stored publication timestamps
    for a given delivery date, allowing the user to compare vintage selections.
    """

    delivery_timestamp: str = Field(..., description="Delivery interval start (UTC ISO-8601)")
    publish_timestamp: str = Field(..., description="Forecast publication timestamp (UTC ISO-8601)")
    generation_mw: float = Field(..., description="Forecast wind generation in MW")
    lead_time_hours: Optional[float] = Field(None, description="Lead time from publish to delivery, hours")
    is_ex_ante: bool = Field(True, description="True if published before delivery interval start")


class ComparisonIntervalSchema(BaseModel):
    """A single 30-minute delivery interval comparison: selected forecast vs. actual.

    The core output of the forecast vs. actual comparison for a delivery date.
    Every interval in the delivery date is represented, even if data is missing.
    """

    delivery_timestamp: str = Field(
        ...,
        description="Delivery interval start time (UTC ISO-8601)"
    )
    delivery_date: str = Field(..., description="Delivery date (Europe/London)")
    settlement_period: Optional[int] = Field(None, description="GB settlement period (1-48)")
    decision_cutoff_utc: str = Field(
        ...,
        description="Decision cutoff used for forecast selection (UTC ISO-8601)"
    )

    # Actual outturn
    actual_generation_mw: Optional[float] = Field(
        None,
        description="Actual wind generation in MW (None if not yet available)"
    )
    is_actual_available: bool = Field(
        ...,
        description="True if actual outturn is stored for this interval"
    )

    # Selected forecast vintage
    forecast_generation_mw: Optional[float] = Field(
        None,
        description="Selected day-ahead forecast in MW (None if no eligible vintage)"
    )
    forecast_publish_timestamp: Optional[str] = Field(
        None,
        description="Publication timestamp of selected forecast vintage (UTC ISO-8601)"
    )
    is_forecast_available: bool = Field(
        ...,
        description="True if an eligible forecast was found"
    )

    # Derived error (only when both actual and forecast are present)
    forecast_error_mw: Optional[float] = Field(
        None,
        description="forecast - actual (positive = overforecast, negative = underforecast)"
    )
    absolute_error_mw: Optional[float] = Field(
        None,
        description="abs(forecast - actual)"
    )
    percentage_error: Optional[float] = Field(
        None,
        description="(forecast - actual) / actual * 100. None when actual == 0 or data missing."
    )
    is_matched: bool = Field(
        ...,
        description="True if both actual and forecast are available for this interval"
    )


class ComparisonSummarySchema(BaseModel):
    """Summary statistics for a delivery date comparison at a given decision cutoff.

    Returned by /api/comparison for a single delivery date.
    """

    delivery_date: str = Field(..., description="Delivery date (e.g. '2026-01-01')")
    decision_cutoff_utc: str = Field(
        ...,
        description="Decision cutoff applied to all intervals (UTC ISO-8601)"
    )
    cutoff_time_local: str = Field(
        ...,
        description="Decision cutoff in Europe/London (HH:MM)"
    )

    # Counts
    total_intervals: int = Field(..., description="Total 30-min delivery intervals in the date")
    matched_intervals: int = Field(..., description="Intervals with both actual and forecast")
    missing_actual_intervals: int = Field(..., description="Intervals without actual outturn")
    missing_forecast_intervals: int = Field(..., description="Intervals without eligible forecast")
    unique_hourly_forecasts: int = Field(
        0, description="Count of distinct hourly WINDFOR forecast records selected"
    )

    # Interval-level details
    intervals: List[ComparisonIntervalSchema] = Field(
        ...,
        description="Per-interval comparison results"
    )


class ComparisonResponseSchema(BaseModel):
    """Response envelope for GET /api/comparison over single-day or multi-day range.

    Guarantees:
    - Cutoff evaluated per delivery date (D-1 at cutoff_time_local in Europe/London).
    - Resolution bridge: native 1-hour WINDFOR forecasts mapped to two 30-min FUELHH actuals.
    - Unique hourly forecasts selected are reported separately from half-hourly covered intervals.
    - Missing data is never converted to zero.
    """

    date_range_start: str = Field(
        ...,
        description="First delivery date in the requested range (Europe/London, inclusive)",
    )
    date_range_end: str = Field(
        ...,
        description="Last delivery date in the requested range (Europe/London, inclusive)",
    )
    date_boundary_type: str = Field(
        "inclusive",
        description="Date boundary specification: both date_range_start and date_range_end are inclusive",
    )
    cutoff_time_local: str = Field(
        ...,
        description="Decision cutoff time in Europe/London (HH:MM). Default: '11:00'",
    )
    cutoff_timezone: str = Field(
        "Europe/London",
        description="Timezone in which cutoff_time_local is specified and evaluated",
    )
    cutoff_rule: str = Field(
        ...,
        description="Human-readable decision cutoff rule applied per delivery date",
    )
    cutoff_applied_per_delivery_date: bool = Field(
        True,
        description="True: decision cutoff is evaluated per delivery date (D-1 at cutoff_time_local)",
    )
    decision_cutoff_utc: str = Field(
        ...,
        description="Reference D-1 decision cutoff UTC timestamp for date_range_start",
    )
    decision_cutoffs_by_date: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-delivery-date map of D-1 decision cutoff timestamps in UTC ISO-8601",
    )

    # Resolution information
    actual_resolution: str = Field(
        "30-minute settlement periods",
        description="Native physical resolution of FUELHH actual generation data",
    )
    forecast_resolution: str = Field(
        "1-hour intervals (WINDFOR)",
        description="Native physical resolution of WINDFOR forecast data",
    )

    # Coverage counts
    expected_interval_count: int = Field(
        ...,
        description="Total expected 30-minute delivery intervals for the date range (days × 48)",
    )
    actual_interval_count: int = Field(
        ...,
        description="Half-hourly intervals with actual outturn available in the database",
    )
    unique_actual_records_count: int = Field(
        ...,
        description="Unique 30-minute actual records present in database for the requested range",
    )
    unique_hourly_forecast_count: int = Field(
        ...,
        description="Number of distinct hourly WINDFOR forecast records selected across the date range",
    )
    forecast_covered_interval_count: int = Field(
        ...,
        description="Half-hourly settlement intervals covered by an eligible day-ahead hourly forecast",
    )
    forecast_interval_count: int = Field(
        ...,
        description="Alias for forecast_covered_interval_count for backward compatibility",
    )
    matched_interval_count: int = Field(
        ...,
        description="Half-hourly settlement intervals where both actual and forecast are present",
    )
    missing_actual_intervals: int = Field(
        ...,
        description="Half-hourly settlement intervals missing actual outturn",
    )
    missing_forecast_intervals: int = Field(
        ...,
        description="Half-hourly settlement intervals missing an eligible day-ahead forecast",
    )

    # Comparison rows
    intervals: List[ComparisonIntervalSchema] = Field(
        ...,
        description="Half-hourly comparison intervals across the requested date range",
    )

