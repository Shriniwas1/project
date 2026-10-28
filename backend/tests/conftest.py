import sys
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Ensure workspace root is in sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.main import app
from backend.app.core.database import Base, engine, AsyncSessionLocal, init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Ensure all database tables are created before running tests."""
    await init_db()
    yield


@pytest_asyncio.fixture
async def async_client():
    """Async HTTP test client fixture bound to the FastAPI ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

