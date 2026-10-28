"""Actuals API route: GET /api/actuals

Returns persisted FUELHH actual wind generation records for a requested delivery date range.
Preserves native half-hourly settlement resolution without implicit ingestion or zero-filling.
"""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.timezone import ensure_utc, format_utc_iso
from backend.app.models.actual import ActualGeneration
from backend.app.schemas.actual import ActualItemSchema, ActualsResponseSchema

router = APIRouter(tags=["Actual Generation"])


@router.get(
    "/actuals",
    response_model=ActualsResponseSchema,
    summary="Actual Wind Generation Records",
    description=(
        "Returns persisted FUELHH WIND outturn generation records for the requested delivery date range. "
        "Native 30-minute settlement periods (SP 1–48) are preserved. "
        "Missing intervals are not coerced to zero; this endpoint is strictly read-only and never triggers ingestion."
    ),
)
async def get_actuals(
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
    db: AsyncSession = Depends(get_db),
) -> ActualsResponseSchema:
    """Return actual generation records in [start_date, end_date] inclusive."""
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail=(
                f"end_date ({end_date}) must be >= start_date ({start_date}). "
                "The date range must be non-empty."
            ),
        )

    stmt = (
        select(ActualGeneration)
        .where(
            and_(
                ActualGeneration.delivery_date >= start_date,
                ActualGeneration.delivery_date <= end_date,
                ActualGeneration.source == "ELEXON_FUELHH",
            )
        )
        .order_by(ActualGeneration.delivery_timestamp.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    records: List[ActualItemSchema] = []
    for row in rows:
        deliv_utc = ensure_utc(row.delivery_timestamp)
        pub_utc = ensure_utc(row.publish_timestamp) if row.publish_timestamp else None
        records.append(
            ActualItemSchema(
                delivery_timestamp=format_utc_iso(deliv_utc),
                delivery_date=str(row.delivery_date),
                settlement_period=row.settlement_period,
                generation_mw=row.generation_mw,
                fuel_type=row.fuel_type,
                source=row.source,
                publish_timestamp=format_utc_iso(pub_utc) if pub_utc else None,
            )
        )

    return ActualsResponseSchema(
        date_range_start=str(start_date),
        date_range_end=str(end_date),
        date_boundary_type="inclusive",
        timezone="Europe/London",
        resolution="30-minute settlement periods (FUELHH)",
        record_count=len(records),
        records=records,
    )
