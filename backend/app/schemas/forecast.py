"""Pydantic schemas for WINDFOR forecast wind generation API responses (Phase 6)."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ForecastItemSchema(BaseModel):
    """A single persisted WINDFOR forecast vintage record."""

    delivery_timestamp: str = Field(
        ...,
        description="UTC start of the 1-hour forecast delivery interval (ISO-8601, e.g. '2026-01-01T12:00:00Z')",
    )
    delivery_date: str = Field(
        ...,
        description="Delivery date in Europe/London (YYYY-MM-DD)",
    )
    publish_timestamp: str = Field(
        ...,
        description="UTC timestamp when this forecast vintage was published by NESO/Elexon (ISO-8601)",
    )
    generation_mw: float = Field(
        ...,
        description="Forecasted wind generation in MW",
    )
    source: str = Field(
        "ELEXON_WINDFOR",
        description="Source dataset identifier",
    )
    lead_time_hours: Optional[float] = Field(
        None,
        description="Lead time in hours: (delivery_timestamp - publish_timestamp)",
    )
    is_ex_ante: bool = Field(
        True,
        description="True if published before delivery interval start (publish_timestamp <= delivery_timestamp)",
    )


class ForecastsResponseSchema(BaseModel):
    """Response envelope for GET /api/forecasts."""

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
    timezone: str = Field(
        "Europe/London",
        description="Business delivery date timezone",
    )
    resolution: str = Field(
        "1-hour intervals (WINDFOR)",
        description="Native physical resolution of WINDFOR forecast data",
    )
    latest_only: bool = Field(
        False,
        description="True if only the latest publication vintage per delivery interval was selected",
    )
    publish_before: Optional[str] = Field(
        None,
        description="Upper bound filter on publication timestamp in UTC ISO-8601 (if applied)",
    )
    record_count: int = Field(
        ...,
        description="Number of forecast records returned in the records array",
    )
    unique_delivery_intervals_count: int = Field(
        ...,
        description="Number of distinct 1-hour delivery intervals covered by the returned records",
    )
    records: List[ForecastItemSchema] = Field(
        ...,
        description="List of persisted forecast records matching the query parameters",
    )
