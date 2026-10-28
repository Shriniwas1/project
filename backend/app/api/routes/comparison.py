"""Comparison API route: GET /api/comparison

Returns half-hourly forecast vs. actual comparison rows for a delivery date range,
applying strict vintage selection at the configured D-1 decision cutoff.
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.schemas.comparison import ComparisonResponseSchema
from backend.app.services.forecast_selection_service import ForecastSelectionService

router = APIRouter(tags=["Forecast Comparison"])
logger = logging.getLogger(__name__)


@router.get(
    "/comparison",
    response_model=ComparisonResponseSchema,
    summary="Forecast vs. Actual Comparison",
    description=(
        "Returns half-hourly comparison rows comparing day-ahead selected WINDFOR forecasts against FUELHH actuals. "
        "Strict vintage selection is applied separately to each delivery date (D-1 at `decision_cutoff` Europe/London). "
        "Each 1-hour forecast maps to two 30-min settlement actuals (resolution bridge). "
        "Missing forecasts or actuals are never coerced to zero. "
        "Per-delivery-date cutoff metadata and 5-way coverage counts are included."
    ),
)
async def get_comparison(
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
    decision_cutoff: Optional[str] = Query(
        None,
        description=(
            "Day-ahead decision cutoff in HH:MM Europe/London on D-1. "
            f"Defaults to project setting ({settings.DEFAULT_DECISION_CUTOFF}). "
            "Example: '11:00'."
        ),
        openapi_examples={"default": {"value": "11:00"}},
    ),
    db: AsyncSession = Depends(get_db),
) -> ComparisonResponseSchema:
    """Return half-hourly comparison rows for [start_date, end_date] inclusive at decision_cutoff."""
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail=(
                f"end_date ({end_date}) must be >= start_date ({start_date}). "
                "The date range must be non-empty."
            ),
        )

    cutoff_str = decision_cutoff or settings.DEFAULT_DECISION_CUTOFF

    # Validate cutoff format
    parts = cutoff_str.strip().split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise HTTPException(
            status_code=422,
            detail=(
                f"decision_cutoff '{cutoff_str}' is not a valid HH:MM time. "
                "Use 24-hour format, e.g. '11:00'."
            ),
        )
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise HTTPException(
            status_code=422,
            detail=(
                f"decision_cutoff '{cutoff_str}' is out of range. "
                "Hour must be 0–23 and minute must be 0–59."
            ),
        )

    try:
        svc = ForecastSelectionService(db=db)
        return await svc.build_comparison_for_date_range(
            date_from=start_date,
            date_to=end_date,
            cutoff_time_str=cutoff_str,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Forecast comparison failed unexpectedly: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error building forecast comparison.")
