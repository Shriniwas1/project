"""Pydantic schemas for FUELHH actual wind generation API responses (Phase 6)."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ActualItemSchema(BaseModel):
    """A single verified half-hourly actual wind generation outturn record from FUELHH."""

    delivery_timestamp: str = Field(
        ...,
        description="UTC start timestamp of the 30-min settlement delivery interval (ISO-8601, e.g. '2026-01-01T00:00:00Z')",
    )
    delivery_date: str = Field(
        ...,
        description="Delivery date in Europe/London (YYYY-MM-DD)",
    )
    settlement_period: int = Field(
        ...,
        description="GB Settlement Period number (1 to 48, or 46/50 on clock-change days)",
    )
    generation_mw: float = Field(
        ...,
        description="Actual wind power outturn delivered to the GB transmission grid in MW",
    )
    fuel_type: str = Field(
        "WIND",
        description="Fuel type category, strictly 'WIND'",
    )
    source: str = Field(
        "ELEXON_FUELHH",
        description="Source dataset identifier",
    )
    publish_timestamp: Optional[str] = Field(
        None,
        description="Settlement run publication timestamp in UTC ISO-8601 (if available)",
    )


class ActualsResponseSchema(BaseModel):
    """Response envelope for GET /api/actuals."""

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
        "30-minute settlement periods (FUELHH)",
        description="Native physical resolution of FUELHH actual generation data",
    )
    record_count: int = Field(
        ...,
        description="Number of actual records returned in the records array",
    )
    records: List[ActualItemSchema] = Field(
        ...,
        description="List of persisted actual generation records for the requested date range",
    )
