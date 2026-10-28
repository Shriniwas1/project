"""Forecasts API route: GET /api/forecasts

Returns persisted WINDFOR forecast records for a requested delivery date range.
Preserves native 1-hour resolution, multi-vintage publication history, and lead times.
"""

from datetime import date
from typing import List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.timezone import ensure_utc, format_utc_iso, parse_iso_to_utc
from backend.app.models.forecast import ForecastGeneration
from backend.app.schemas.forecast import ForecastItemSchema, ForecastsResponseSchema

router = APIRouter(tags=["Forecast Generation"])


@router.get(
    "/forecasts",
    response_model=ForecastsResponseSchema,
    summary="Forecast Wind Generation Records",
    description=(
        "Returns persisted WINDFOR forecast records for the requested delivery date range. "
        "Native 1-hour intervals are preserved. "
        "By default, all historical publication vintages are returned. "
        "Pass `latest_only=true` to retrieve only the most recent publication for each interval, "
        "or `publish_before` to filter to forecasts published at or before a specific timestamp."
    ),
)
async def get_forecasts(
    start_date: date = Query(
        ...,
        description="First delivery date (inclusive, Europe/London), e.g. '2026-01-01'",
        openapi_examples={"jan_start": {"value": "2026-01-01"}},
    ),
    end_date: date = Query(
        ...,
        description="Last delivery date (inclusive, Europe/London), e.g. '2026-01-02'",
        openapi_examples={"jan_end": {"value": "2026-01-02"}},
    ),
    latest_only: bool = Query(
        False,
        description="If true, returns only the latest publication vintage for each 1-hour delivery interval.",
        openapi_examples={"all_vintages": {"value": False}, "latest_only": {"value": True}},
    ),
    publish_before: Optional[str] = Query(
        None,
        description="Optional filter: only include forecasts published at or before this timestamp (UTC ISO-8601).",
        openapi_examples={"cutoff_example": {"value": "2025-12-31T11:00:00Z"}},
    ),
    db: AsyncSession = Depends(get_db),
) -> ForecastsResponseSchema:
    """Return forecast records in [start_date, end_date] inclusive."""
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail=(
                f"end_date ({end_date}) must be >= start_date ({start_date}). "
                "The date range must be non-empty."
            ),
        )

    filters = [
        ForecastGeneration.delivery_date >= start_date,
        ForecastGeneration.delivery_date <= end_date,
        ForecastGeneration.source == "ELEXON_WINDFOR",
    ]

    if publish_before is not None:
        try:
            pub_before_utc = parse_iso_to_utc(publish_before)
            filters.append(ForecastGeneration.publish_timestamp <= pub_before_utc)
        except Exception:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"publish_before '{publish_before}' is not a valid ISO-8601 timestamp string. "
                    "Example format: '2025-12-31T11:00:00Z'."
                ),
            )

    stmt = (
        select(ForecastGeneration)
        .where(and_(*filters))
        .order_by(
            ForecastGeneration.delivery_timestamp.asc(),
            ForecastGeneration.publish_timestamp.desc(),
        )
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Filter to latest_only if requested
    filtered_rows: List[ForecastGeneration] = []
    if latest_only:
        seen_delivery_ts: Set[str] = set()
        for row in rows:
            ts_str = str(row.delivery_timestamp)
            if ts_str not in seen_delivery_ts:
                seen_delivery_ts.add(ts_str)
                filtered_rows.append(row)
    else:
        filtered_rows = list(rows)

    # Convert to schema items and count unique delivery intervals
    records: List[ForecastItemSchema] = []
    unique_deliv_set: Set[str] = set()

    for row in filtered_rows:
        deliv_utc = ensure_utc(row.delivery_timestamp)
        pub_utc = ensure_utc(row.publish_timestamp)
        deliv_iso = format_utc_iso(deliv_utc)
        pub_iso = format_utc_iso(pub_utc)
        unique_deliv_set.add(deliv_iso)

        lead_hours = (deliv_utc - pub_utc).total_seconds() / 3600.0
        records.append(
            ForecastItemSchema(
                delivery_timestamp=deliv_iso,
                delivery_date=str(row.delivery_date),
                publish_timestamp=pub_iso,
                generation_mw=row.generation_mw,
                source=row.source,
                lead_time_hours=round(lead_hours, 4),
                is_ex_ante=row.is_ex_ante,
            )
        )

    return ForecastsResponseSchema(
        date_range_start=str(start_date),
        date_range_end=str(end_date),
        date_boundary_type="inclusive",
        timezone="Europe/London",
        resolution="1-hour intervals (WINDFOR)",
        latest_only=latest_only,
        publish_before=publish_before,
        record_count=len(records),
        unique_delivery_intervals_count=len(unique_deliv_set),
        records=records,
    )
