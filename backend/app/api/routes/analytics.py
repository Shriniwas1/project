"""Analytics API route: GET /api/analytics

Returns forecast accuracy metrics (MAE, RMSE, Bias, MAPE) and coverage counts
for a requested delivery date range at a configurable decision cutoff.

All business logic is delegated to AccuracyService (Phase 5) and
ForecastSelectionService (Phase 4). This route only handles request validation
and response serialisation.
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.schemas.analytics import AccuracyMetricsSchema
from backend.app.services.accuracy_service import AccuracyService

router = APIRouter(tags=["Accuracy Analytics"])
logger = logging.getLogger(__name__)


@router.get(
    "/analytics",
    response_model=AccuracyMetricsSchema,
    summary="Forecast Accuracy Metrics",
    description=(
        "Returns MAE, RMSE, Bias, and MAPE for the requested delivery date range "
        "using the strict day-ahead forecast selection engine. "
        "Only forecasts published at or before D-1 at `decision_cutoff` are used. "
        "Coverage counts (matched, missing, zero-actual) are always reported alongside metrics."
    ),
)
async def get_analytics(
    start_date: date = Query(
        ...,
        description="First delivery date (inclusive), e.g. '2026-01-01'.",
        openapi_examples={"jan_start": {"value": "2026-01-01"}},
    ),
    end_date: date = Query(
        ...,
        description="Last delivery date (inclusive), e.g. '2026-01-31'.",
        openapi_examples={"jan_end": {"value": "2026-01-31"}},
    ),
    decision_cutoff: Optional[str] = Query(
        None,
        description=(
            "Day-ahead decision cutoff in HH:MM Europe/London on D-1. "
            f"Defaults to the project setting ({settings.DEFAULT_DECISION_CUTOFF}). "
            "Example: '11:00'."
        ),
        openapi_examples={"default": {"value": "11:00"}},
    ),
    db: AsyncSession = Depends(get_db),
) -> AccuracyMetricsSchema:
    """Return accuracy metrics for [start_date, end_date] inclusive at the given cutoff."""

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
        svc = AccuracyService(db=db)
        return await svc.compute_accuracy(
            date_from=start_date,
            date_to=end_date,
            cutoff_time_str=cutoff_str,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Analytics computation failed unexpectedly: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error computing forecast accuracy analytics.")
