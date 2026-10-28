"""API routes for triggering ingestion and reviewing dataset coverage."""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.ingestion import IngestionResultSchema, CoverageReportSchema
from backend.app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/ingestion", tags=["Data Ingestion & Coverage"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=CoverageReportSchema, summary="Get January 2026 Dataset Coverage")
async def get_ingestion_status(db: AsyncSession = Depends(get_db)) -> CoverageReportSchema:
    """Return rigorous data coverage report for January 2026 actuals and forecasts."""
    service = IngestionService(db=db)
    return await service.get_january_coverage_report()


@router.post("/trigger", response_model=List[IngestionResultSchema], summary="Trigger Ingestion for January 2026")
async def trigger_ingestion(db: AsyncSession = Depends(get_db)) -> List[IngestionResultSchema]:
    """Trigger ingestion of January 2026 FUELHH actuals and WINDFOR forecasts."""
    service = IngestionService(db=db)
    try:
        act_res, fc_res = await service.ingest_january_2026()
        return [act_res, fc_res]
    except Exception as exc:
        logger.exception("Ingestion failed unexpectedly: %s", exc)
        raise HTTPException(status_code=500, detail="Data ingestion failed.")
