import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["database_connected"] is True
    assert data["version"] == "1.0.0"
    assert "Europe/London" in data["default_decision_cutoff"]
    assert "January 2026" in data["dataset_scope"]


@pytest.mark.asyncio
async def test_root_redirect_to_docs(async_client: AsyncClient):
    response = await async_client.get("/", follow_redirects=False)
    assert response.status_code in [302, 307]
    assert response.headers["location"] == "/docs"
