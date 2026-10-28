import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_ingestion_status(async_client: AsyncClient):
    """Verify GET /api/ingestion/status returns valid January 2026 coverage structure."""
    response = await async_client.get("/api/ingestion/status")
    assert response.status_code == 200
    data = response.json()
    assert data["target_period"] == "2026-01-01 to 2026-01-31"
    assert data["expected_actual_intervals"] == 1488
    assert data["expected_hourly_forecast_intervals"] == 744
    assert "stored_actual_intervals" in data
    assert "stored_forecast_vintages_count" in data
    assert "resolutions" in data
    assert data["resolutions"]["actuals"] == "30-minute settlement periods (48/day)"
    assert data["resolutions"]["forecasts"] == "1-hour intervals (24/day)"
