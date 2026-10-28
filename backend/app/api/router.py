from fastapi import APIRouter
from backend.app.api.routes import (
    health,
    ingestion,
    analytics,
    actuals,
    forecasts,
    comparison,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(ingestion.router)
api_router.include_router(analytics.router)
api_router.include_router(actuals.router)
api_router.include_router(forecasts.router)
api_router.include_router(comparison.router)
