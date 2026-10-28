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
