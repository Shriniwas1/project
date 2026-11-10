from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from backend.app.core.config import settings
from backend.app.api.router import api_router


from backend.app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown routines."""
    # Ensure database tables exist
    await init_db()
    
    # Auto-seed January 2026 data on startup if database is empty (e.g. on fresh Render deploys)
    try:
        from backend.app.core.database import AsyncSessionLocal
        from backend.app.models.actual import ActualGeneration
        from backend.app.services.ingestion_service import IngestionService
        from sqlalchemy import select, func
        
        async with AsyncSessionLocal() as session:
            count_stmt = select(func.count(ActualGeneration.id))
            count_res = await session.execute(count_stmt)
            count = count_res.scalar() or 0
            if count == 0:
                import logging
                logging.getLogger(__name__).info("Database is empty on startup. Automatically seeding January 2026 data from Elexon BMRS...")
                ingestion_svc = IngestionService(db=session)
                await ingestion_svc.ingest_january_2026()
                logging.getLogger(__name__).info("Auto-seeding complete! January 2026 data is ready.")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Auto-seeding check encountered non-fatal error: {e}")
        
    yield
    # Shutdown actions


app = FastAPI(
    title="Wind Procurement Intelligence API",
    description="UK Day-Ahead Wind Generation Forecasting and Accuracy Analysis Service.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware configuration
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [str(settings.CORS_ORIGINS)]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if "*" not in origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include main API router under /api
app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")
