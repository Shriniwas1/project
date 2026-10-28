import os
from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from backend.app.core.config import settings

# Ensure sqlite data directory exists
if settings.DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

# Create asynchronous engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

from datetime import datetime, timezone
from sqlalchemy import TypeDecorator, DateTime
from backend.app.core.timezone import ensure_utc

Base = declarative_base()


class UTCDateTime(TypeDecorator):
    """Platform-independent UTC DateTime column type.
    
    Ensures datetime is saved in UTC and always loaded back as timezone-aware UTC datetime.
    """
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, str):
                from backend.app.core.timezone import parse_iso_to_utc
                value = parse_iso_to_utc(value)
            return ensure_utc(value).replace(tzinfo=None)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return None



async def init_db() -> None:
    """Create all database tables asynchronously if they do not exist."""
    # Import models locally to register them on Base.metadata
    from backend.app.models.actual import ActualGeneration
    from backend.app.models.forecast import ForecastGeneration
    from backend.app.models.audit import IngestionLog

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

