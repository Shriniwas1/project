from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.timezone import format_utc_iso
from backend.app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Service Health and Status")
async def get_health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Return application operational health, database connectivity status, and default assumptions."""
    db_connected = False
    actual_count = 0
    forecast_count = 0
    
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_connected = True
            
        # Try checking table counts if tables exist
        try:
            act_res = await db.execute(text("SELECT COUNT(*) FROM actual_generation"))
            actual_count = act_res.scalar() or 0
        except Exception:
            pass
            
        try:
            fc_res = await db.execute(text("SELECT COUNT(*) FROM forecast_generation"))
            forecast_count = fc_res.scalar() or 0
        except Exception:
            pass
            
    except Exception:
        db_connected = False

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        database_connected=db_connected,
        timestamp_utc=format_utc_iso(datetime.now(timezone.utc)),
        dataset_scope="January 2026 UK Wind Procurement",
        actual_records_count=actual_count,
        forecast_records_count=forecast_count,
        default_decision_cutoff=f"{settings.DEFAULT_DECISION_CUTOFF} {settings.DEFAULT_TIMEZONE}"
    )
