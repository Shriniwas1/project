import json
from datetime import date, datetime
from pathlib import Path
import pytest
import httpx

from backend.app.clients.elexon_client import (
    ElexonClient,
    ElexonError,
    ElexonRateLimitError,
)
from backend.app.core.timezone import UTC_TZ
from backend.app.schemas.elexon import FuelhhWindRecord, WindforForecastRecord

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fuelhh_sample_data():
    with open(FIXTURES_DIR / "fuelhh_sample.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def windfor_sample_data():
    with open(FIXTURES_DIR / "windfor_sample.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_fixture_loading(fuelhh_sample_data, windfor_sample_data):
    """Verify fixture JSON files exist and contain valid structures."""
    assert len(fuelhh_sample_data) == 5
    assert len(windfor_sample_data) == 5


@pytest.mark.asyncio
async def test_fuelhh_parsing_and_wind_filtering(fuelhh_sample_data):
    """Verify FUELHH stream parsing and strict filtering for fuelType == 'WIND'."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert "datasets/FUELHH/stream" in str(request.url)
        return httpx.Response(200, json=fuelhh_sample_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ElexonClient(client=http_client)
        records = await client.fetch_actual_wind_generation(
            settlement_date_from=date(2026, 1, 1),
            settlement_date_to=date(2026, 1, 1),
            chunk_days=3
        )

        # 3 out of 5 sample records are WIND (NUCLEAR and CCGT must be filtered out)
        assert len(records) == 3
        for r in records:
            assert isinstance(r, FuelhhWindRecord)
            assert r.fuel_type == "WIND"
            assert r.generation_mw > 0
            assert r.start_time.tzinfo == UTC_TZ

        # Verify exact generation values preserved
        assert records[0].generation_mw == 14250.0
        assert records[0].settlement_period == 1
        assert records[1].generation_mw == 14500.5
        assert records[1].settlement_period == 2
        assert records[2].generation_mw == 16200.0
        assert records[2].settlement_period == 24


@pytest.mark.asyncio
async def test_windfor_parsing_and_vintage_preservation(windfor_sample_data):
    """Verify WINDFOR stream parsing and preservation of distinct publication vintages."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert "datasets/WINDFOR/stream" in str(request.url)
        return httpx.Response(200, json=windfor_sample_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ElexonClient(client=http_client)
        forecasts = await client.fetch_wind_forecasts(
            publish_time_from=datetime(2025, 12, 31, 0, 0, 0, tzinfo=UTC_TZ),
            publish_time_to=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC_TZ),
            chunk_days=3
        )

        assert len(forecasts) == 5
        for f in forecasts:
            assert isinstance(f, WindforForecastRecord)
            assert f.dataset == "WINDFOR"
            assert f.start_time.tzinfo == UTC_TZ
            assert f.publish_time.tzinfo == UTC_TZ

        # Check the 3 vintages for 2026-01-01T12:00:00Z are all preserved
        target_interval_forecasts = [
            f for f in forecasts if f.start_time == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
        ]
        assert len(target_interval_forecasts) == 3
        pub_times = [f.publish_time.hour for f in target_interval_forecasts]
        assert sorted(pub_times) == [7, 9, 11]  # 07:30, 09:30, 11:30 vintages


@pytest.mark.asyncio
async def test_missing_or_malformed_records():
    """Verify invalid/missing fields are safely skipped without failing the entire stream."""
    malformed_payload = [
        # Valid
        {
            "dataset": "FUELHH",
            "startTime": "2026-01-01T00:00:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 1,
            "fuelType": "WIND",
            "generation": 12000.0
        },
        # Missing generation
        {
            "dataset": "FUELHH",
            "startTime": "2026-01-01T00:30:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 2,
            "fuelType": "WIND"
        },
        # Negative generation
        {
            "dataset": "FUELHH",
            "startTime": "2026-01-01T01:00:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 3,
            "fuelType": "WIND",
            "generation": -50.0
        },
        # Non-numeric generation
        {
            "dataset": "FUELHH",
            "startTime": "2026-01-01T01:30:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 4,
            "fuelType": "WIND",
            "generation": "UNKNOWN_ERROR"
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=malformed_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ElexonClient(client=http_client)
        records = await client.fetch_actual_wind_generation(
            settlement_date_from=date(2026, 1, 1),
            settlement_date_to=date(2026, 1, 1)
        )
        # Only the 1 valid record should be accepted
        assert len(records) == 1
        assert records[0].generation_mw == 12000.0


@pytest.mark.asyncio
async def test_empty_api_response():
    """Verify handling of empty response from API."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ElexonClient(client=http_client)
        records = await client.fetch_actual_wind_generation(
            settlement_date_from=date(2026, 1, 1),
            settlement_date_to=date(2026, 1, 1)
        )
        assert records == []


@pytest.mark.asyncio
async def test_retry_on_429_rate_limit(fuelhh_sample_data):
    """Verify client retries when receiving HTTP 429 and succeeds on subsequent attempt."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "0.01"})
        return httpx.Response(200, json=fuelhh_sample_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ElexonClient(client=http_client, max_retries=2, backoff_factor=0.01)
        records = await client.fetch_actual_wind_generation(
            settlement_date_from=date(2026, 1, 1),
            settlement_date_to=date(2026, 1, 1)
        )
        assert call_count == 2
        assert len(records) == 3


@pytest.mark.asyncio
async def test_retry_on_500_server_error(fuelhh_sample_data):
    """Verify client retries on HTTP 500 server error and succeeds on subsequent attempt."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, text="Internal Server Error")
        return httpx.Response(200, json=fuelhh_sample_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ElexonClient(client=http_client, max_retries=2, backoff_factor=0.01)
        records = await client.fetch_actual_wind_generation(
            settlement_date_from=date(2026, 1, 1),
            settlement_date_to=date(2026, 1, 1)
        )
        assert call_count == 2
        assert len(records) == 3


@pytest.mark.asyncio
async def test_exhausted_retries_raises_rate_limit_error():
    """Verify ElexonRateLimitError is raised when 429 retries are exhausted."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0.01"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ElexonClient(client=http_client, max_retries=1, backoff_factor=0.01)
        with pytest.raises(ElexonRateLimitError):
            await client.fetch_actual_wind_generation(
                settlement_date_from=date(2026, 1, 1),
                settlement_date_to=date(2026, 1, 1)
            )


def test_chunk_date_boundaries():
    """Verify date range splitting into chunk_days slices."""
    client = ElexonClient()
    slices = client._split_date_range(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 7),
        chunk_days=3
    )
    # Day 1-3, Day 4-6, Day 7-7
    assert len(slices) == 3
    assert slices[0] == (date(2026, 1, 1), date(2026, 1, 3))
    assert slices[1] == (date(2026, 1, 4), date(2026, 1, 6))
    assert slices[2] == (date(2026, 1, 7), date(2026, 1, 7))


def test_forecast_published_before_delivery_ex_ante():
    """Verify that a forecast published prior to delivery interval is flagged as ex-ante with positive lead time."""
    record = WindforForecastRecord(
        start_time="2026-01-01T12:00:00Z",
        publish_time="2025-12-31T09:30:00Z",
        generation_mw=15000.0
    )
    assert record.is_ex_ante is True
    assert record.lead_time_hours == 26.5  # 26.5 hours ahead
    assert record.start_time.tzinfo == UTC_TZ
    assert record.publish_time.tzinfo == UTC_TZ


def test_forecast_published_after_delivery_retrospective():
    """Verify that retrospective records in sliding batches have negative lead time and can be filtered."""
    # This exact pair mirrors the verified live batch sample from NESO
    retrospective_raw = {
        "dataset": "WINDFOR",
        "publishTime": "2025-12-31T02:30:00Z",
        "startTime": "2025-12-30T21:00:00Z",
        "generation": 6086.0
    }
    rec = WindforForecastRecord(
        start_time=retrospective_raw["startTime"],
        publish_time=retrospective_raw["publishTime"],
        generation_mw=retrospective_raw["generation"]
    )
    # Delivery (2025-12-30 21:00) is 5.5 hours BEFORE publication (2025-12-31 02:30)
    assert rec.is_ex_ante is False
    assert rec.lead_time_hours == -5.5
    assert rec.start_time < rec.publish_time


@pytest.mark.asyncio
async def test_ex_ante_filter_behavior():
    """Verify that ex_ante_only=True filters out retrospective records while ex_ante_only=False retains them."""
    batch_payload = [
        # Retrospective record (anchor period of batch)
        {
            "dataset": "WINDFOR",
            "publishTime": "2025-12-31T02:30:00Z",
            "startTime": "2025-12-30T21:00:00Z",
            "generation": 6086.0
        },
        # Ex-ante record (day-ahead forecast)
        {
            "dataset": "WINDFOR",
            "publishTime": "2025-12-31T02:30:00Z",
            "startTime": "2026-01-01T12:00:00Z",
            "generation": 14500.0
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=batch_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ElexonClient(client=http_client)

        # 1. With ex_ante_only=True, only the genuine forecast is returned
        ex_ante_results = await client.fetch_wind_forecasts(
            publish_time_from=datetime(2025, 12, 31, 0, 0, 0, tzinfo=UTC_TZ),
            publish_time_to=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC_TZ),
            ex_ante_only=True
        )
        assert len(ex_ante_results) == 1
        assert ex_ante_results[0].start_time == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)

        # 2. With ex_ante_only=False, both are retained with audit flags
        all_results = await client.fetch_wind_forecasts(
            publish_time_from=datetime(2025, 12, 31, 0, 0, 0, tzinfo=UTC_TZ),
            publish_time_to=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC_TZ),
            ex_ante_only=False
        )
        assert len(all_results) == 2
        assert all_results[0].is_ex_ante is False
        assert all_results[1].is_ex_ante is True


def test_independent_timestamp_preservation():
    """Verify that publish_time and start_time are strictly independent and neither is derived from the other."""
    raw = {
        "dataset": "WINDFOR",
        "publishTime": "2025-12-31T09:30:00Z",
        "startTime": "2026-01-01T18:00:00Z",
        "generation": 17200.0
    }
    rec = WindforForecastRecord(
        start_time=raw["startTime"],
        publish_time=raw["publishTime"],
        generation_mw=raw["generation"]
    )
    assert rec.publish_time == datetime(2025, 12, 31, 9, 30, 0, tzinfo=UTC_TZ)
    assert rec.start_time == datetime(2026, 1, 1, 18, 0, 0, tzinfo=UTC_TZ)
    # Explicitly verify they are distinct objects with different calendar dates
    assert rec.publish_time.day == 31
    assert rec.start_time.day == 1
    assert rec.publish_time != rec.start_time

