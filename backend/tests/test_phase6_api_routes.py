"""Phase 6 tests: Comparison, Actuals, and Forecasts API Routes.

Covers:
- GET /api/actuals: valid date range, empty DB, missing dates, date boundaries, invalid date input, read-only behavior.
- GET /api/forecasts: valid date range, empty DB, multiple publication vintages, publication timestamps preserved, hourly resolution, latest_only filter, publish_before filter, invalid date/timestamp input, read-only behavior.
- GET /api/comparison: valid single-day and multi-day requests, per-delivery-date cutoff behavior, exact cutoff boundary, forecast after cutoff excluded, missing actual, missing forecast, multiple vintages, hourly-to-half-hourly mapping, unique forecast count vs covered intervals, coverage counts, invalid inputs, empty DB.
"""

from datetime import date, datetime
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from sqlalchemy import select, func

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.core.timezone import UTC_TZ, get_delivery_date_for_interval, calculate_settlement_period
from backend.app.models.actual import ActualGeneration
from backend.app.models.forecast import ForecastGeneration


# ---------------------------------------------------------------------------
# Test Fixture: Isolated in-memory DB shared by client and test
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def isolated_client_and_db():
    """Provides an isolated in-memory DB and test client for Phase 6 API tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def override_get_db():
        async with TestSession() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, TestSession

    app.dependency_overrides.clear()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers to seed DB records
# ---------------------------------------------------------------------------

async def _add_actual(session, delivery_ts: datetime, generation_mw: float, fuel_type: str = "WIND") -> ActualGeneration:
    row = ActualGeneration(
        delivery_timestamp=delivery_ts,
        delivery_date=get_delivery_date_for_interval(delivery_ts),
        settlement_period=calculate_settlement_period(delivery_ts),
        generation_mw=generation_mw,
        fuel_type=fuel_type,
        source="ELEXON_FUELHH",
    )
    session.add(row)
    await session.commit()
    return row


async def _add_forecast(
    session, delivery_ts: datetime, publish_ts: datetime, generation_mw: float
) -> ForecastGeneration:
    row = ForecastGeneration(
        delivery_timestamp=delivery_ts,
        delivery_date=get_delivery_date_for_interval(delivery_ts),
        publish_timestamp=publish_ts,
        generation_mw=generation_mw,
        source="ELEXON_WINDFOR",
        lead_time_hours=(delivery_ts - publish_ts).total_seconds() / 3600.0,
        is_ex_ante=publish_ts <= delivery_ts,
    )
    session.add(row)
    await session.commit()
    return row


# ===========================================================================
# 1. ACTUALS ENDPOINT: GET /api/actuals
# ===========================================================================

@pytest.mark.asyncio
async def test_actuals_valid_date_range(isolated_client_and_db):
    """GET /api/actuals returns 200, correct metadata, and ordered actual records."""
    client, Session = isolated_client_and_db

    ts1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ)
    ts2 = datetime(2026, 1, 1, 0, 30, 0, tzinfo=UTC_TZ)
    async with Session() as session:
        await _add_actual(session, ts1, 12500.0)
        await _add_actual(session, ts2, 12800.0)

    resp = await client.get("/api/actuals?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()

    assert data["date_range_start"] == "2026-01-01"
    assert data["date_range_end"] == "2026-01-01"
    assert data["date_boundary_type"] == "inclusive"
    assert data["timezone"] == "Europe/London"
    assert "30-minute" in data["resolution"]
    assert data["record_count"] == 2
    assert len(data["records"]) == 2

    # Check fields of records
    rec1, rec2 = data["records"][0], data["records"][1]
    assert rec1["delivery_timestamp"] == "2026-01-01T00:00:00Z"
    assert rec1["settlement_period"] == 1
    assert rec1["generation_mw"] == 12500.0
    assert rec1["fuel_type"] == "WIND"
    assert rec1["source"] == "ELEXON_FUELHH"

    assert rec2["delivery_timestamp"] == "2026-01-01T00:30:00Z"
    assert rec2["settlement_period"] == 2
    assert rec2["generation_mw"] == 12800.0


@pytest.mark.asyncio
async def test_actuals_empty_database(isolated_client_and_db):
    """GET /api/actuals with no records returns 200 and empty records array."""
    client, _ = isolated_client_and_db
    resp = await client.get("/api/actuals?start_date=2026-01-10&end_date=2026-01-11")
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_count"] == 0
    assert data["records"] == []


@pytest.mark.asyncio
async def test_actuals_missing_dates_no_zero_fill(isolated_client_and_db):
    """Missing settlement periods or dates are omitted, never filled with zero MW."""
    client, Session = isolated_client_and_db

    # Only add one record on Jan 1
    ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    async with Session() as session:
        await _add_actual(session, ts, 14000.0)

    # Query range covering Jan 1 to Jan 3
    resp = await client.get("/api/actuals?start_date=2026-01-01&end_date=2026-01-03")
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_count"] == 1
    assert data["records"][0]["generation_mw"] == 14000.0
    # No records for Jan 2 or Jan 3 were fabricated
    dates = {r["delivery_date"] for r in data["records"]}
    assert dates == {"2026-01-01"}


@pytest.mark.asyncio
async def test_actuals_date_boundaries_inclusive(isolated_client_and_db):
    """Boundary test: records on start_date and end_date included; records outside excluded."""
    client, Session = isolated_client_and_db

    ts_before = datetime(2025, 12, 31, 23, 30, 0, tzinfo=UTC_TZ)
    ts_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ)
    ts_end = datetime(2026, 1, 2, 23, 30, 0, tzinfo=UTC_TZ)
    ts_after = datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_actual(session, ts_before, 9000.0)
        await _add_actual(session, ts_start, 10000.0)
        await _add_actual(session, ts_end, 11000.0)
        await _add_actual(session, ts_after, 12000.0)

    resp = await client.get("/api/actuals?start_date=2026-01-01&end_date=2026-01-02")
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_count"] == 2
    timestamps = [r["delivery_timestamp"] for r in data["records"]]
    assert timestamps == ["2026-01-01T00:00:00Z", "2026-01-02T23:30:00Z"]


@pytest.mark.asyncio
async def test_actuals_invalid_date_input_422(isolated_client_and_db):
    """Invalid date range (start > end) or malformed date returns 422."""
    client, _ = isolated_client_and_db

    # start > end
    resp = await client.get("/api/actuals?start_date=2026-01-05&end_date=2026-01-01")
    assert resp.status_code == 422

    # Malformed date string
    resp2 = await client.get("/api/actuals?start_date=2026-01-99&end_date=2026-01-01")
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_actuals_no_implicit_ingestion(isolated_client_and_db):
    """GET /api/actuals is purely read-only and never modifies database records."""
    client, Session = isolated_client_and_db

    async with Session() as session:
        count_before = await session.scalar(select(func.count(ActualGeneration.id)))

    resp = await client.get("/api/actuals?start_date=2026-01-01&end_date=2026-01-02")
    assert resp.status_code == 200

    async with Session() as session:
        count_after = await session.scalar(select(func.count(ActualGeneration.id)))

    assert count_before == count_after == 0


# ===========================================================================
# 2. FORECASTS ENDPOINT: GET /api/forecasts
# ===========================================================================

@pytest.mark.asyncio
async def test_forecasts_valid_date_range(isolated_client_and_db):
    """GET /api/forecasts returns 200, correct resolution, and forecast records."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    pub_ts = datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_forecast(session, deliv_ts, pub_ts, 15000.0)

    resp = await client.get("/api/forecasts?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()

    assert data["date_range_start"] == "2026-01-01"
    assert data["date_range_end"] == "2026-01-01"
    assert data["timezone"] == "Europe/London"
    assert "1-hour" in data["resolution"]
    assert data["latest_only"] is False
    assert data["record_count"] == 1
    assert data["unique_delivery_intervals_count"] == 1

    rec = data["records"][0]
    assert rec["delivery_timestamp"] == "2026-01-01T10:00:00Z"
    assert rec["publish_timestamp"] == "2025-12-31T08:00:00Z"
    assert rec["generation_mw"] == 15000.0
    assert rec["source"] == "ELEXON_WINDFOR"
    assert rec["is_ex_ante"] is True
    assert rec["lead_time_hours"] == pytest.approx(26.0, rel=1e-4)


@pytest.mark.asyncio
async def test_forecasts_empty_database(isolated_client_and_db):
    """GET /api/forecasts with no records returns 200 and empty records array."""
    client, _ = isolated_client_and_db
    resp = await client.get("/api/forecasts?start_date=2026-01-10&end_date=2026-01-11")
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_count"] == 0
    assert data["unique_delivery_intervals_count"] == 0
    assert data["records"] == []


@pytest.mark.asyncio
async def test_forecasts_multiple_vintages_preserved_by_default(isolated_client_and_db):
    """By default, all historical publication vintages for an interval are preserved and returned."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ)
    pub1 = datetime(2025, 12, 31, 6, 0, 0, tzinfo=UTC_TZ)
    pub2 = datetime(2025, 12, 31, 9, 0, 0, tzinfo=UTC_TZ)
    pub3 = datetime(2025, 12, 31, 12, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_forecast(session, deliv_ts, pub1, 11000.0)
        await _add_forecast(session, deliv_ts, pub2, 12000.0)
        await _add_forecast(session, deliv_ts, pub3, 13000.0)

    resp = await client.get("/api/forecasts?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()

    assert data["record_count"] == 3
    assert data["unique_delivery_intervals_count"] == 1
    pub_times = [r["publish_timestamp"] for r in data["records"]]
    assert len(pub_times) == 3
    assert "2025-12-31T06:00:00Z" in pub_times
    assert "2025-12-31T09:00:00Z" in pub_times
    assert "2025-12-31T12:00:00Z" in pub_times


@pytest.mark.asyncio
async def test_forecasts_latest_only_filter(isolated_client_and_db):
    """latest_only=true returns only the single latest publication vintage per delivery interval."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ)
    pub1 = datetime(2025, 12, 31, 6, 0, 0, tzinfo=UTC_TZ)
    pub2 = datetime(2025, 12, 31, 12, 0, 0, tzinfo=UTC_TZ)  # latest

    async with Session() as session:
        await _add_forecast(session, deliv_ts, pub1, 11000.0)
        await _add_forecast(session, deliv_ts, pub2, 13000.0)

    resp = await client.get("/api/forecasts?start_date=2026-01-01&end_date=2026-01-01&latest_only=true")
    assert resp.status_code == 200
    data = resp.json()

    assert data["latest_only"] is True
    assert data["record_count"] == 1
    assert data["unique_delivery_intervals_count"] == 1
    assert data["records"][0]["publish_timestamp"] == "2025-12-31T12:00:00Z"
    assert data["records"][0]["generation_mw"] == 13000.0


@pytest.mark.asyncio
async def test_forecasts_publish_before_filter(isolated_client_and_db):
    """publish_before filters forecasts to those published at or before the given timestamp."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ)
    pub_early = datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ)
    pub_late = datetime(2025, 12, 31, 12, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_forecast(session, deliv_ts, pub_early, 10500.0)
        await _add_forecast(session, deliv_ts, pub_late, 12500.0)

    # Filter with publish_before at 10:00 (excludes pub_late)
    resp = await client.get(
        "/api/forecasts?start_date=2026-01-01&end_date=2026-01-01&publish_before=2025-12-31T10:00:00Z"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_count"] == 1
    assert data["records"][0]["publish_timestamp"] == "2025-12-31T08:00:00Z"


@pytest.mark.asyncio
async def test_forecasts_invalid_inputs_422(isolated_client_and_db):
    """Malformed date range or invalid publish_before format returns 422."""
    client, _ = isolated_client_and_db

    # start_date > end_date
    resp1 = await client.get("/api/forecasts?start_date=2026-01-10&end_date=2026-01-05")
    assert resp1.status_code == 422

    # invalid publish_before
    resp2 = await client.get(
        "/api/forecasts?start_date=2026-01-01&end_date=2026-01-01&publish_before=not-a-timestamp"
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_forecasts_no_implicit_ingestion(isolated_client_and_db):
    """GET /api/forecasts is read-only and does not write or mutate database rows."""
    client, Session = isolated_client_and_db

    async with Session() as session:
        count_before = await session.scalar(select(func.count(ForecastGeneration.id)))

    resp = await client.get("/api/forecasts?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200

    async with Session() as session:
        count_after = await session.scalar(select(func.count(ForecastGeneration.id)))

    assert count_before == count_after == 0


# ===========================================================================
# 3. COMPARISON ENDPOINT: GET /api/comparison
# ===========================================================================

@pytest.mark.asyncio
async def test_comparison_valid_one_day_request(isolated_client_and_db):
    """GET /api/comparison for a single day returns 48 intervals and cutoff metadata."""
    client, Session = isolated_client_and_db

    # 10:00 and 10:30 actuals
    ts_10_00 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    ts_10_30 = datetime(2026, 1, 1, 10, 30, 0, tzinfo=UTC_TZ)
    # 1-hour forecast for 10:00
    fc_ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    pub_ts = datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_actual(session, ts_10_00, 10000.0)
        await _add_actual(session, ts_10_30, 10200.0)
        await _add_forecast(session, fc_ts, pub_ts, 10500.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01&decision_cutoff=11:00")
    assert resp.status_code == 200
    data = resp.json()

    assert data["date_range_start"] == "2026-01-01"
    assert data["date_range_end"] == "2026-01-01"
    assert data["cutoff_time_local"] == "11:00"
    assert data["cutoff_applied_per_delivery_date"] is True
    assert data["decision_cutoffs_by_date"] == {"2026-01-01": "2025-12-31T11:00:00Z"}
    assert data["expected_interval_count"] == 48
    assert data["actual_interval_count"] == 2
    assert data["unique_actual_records_count"] == 2
    assert data["unique_hourly_forecast_count"] == 1
    assert data["forecast_covered_interval_count"] == 2
    assert data["matched_interval_count"] == 2
    assert len(data["intervals"]) == 48

    # Verify error calculation on matched intervals
    int_10_00 = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-01T10:00:00Z"][0]
    assert int_10_00["is_matched"] is True
    assert int_10_00["actual_generation_mw"] == 10000.0
    assert int_10_00["forecast_generation_mw"] == 10500.0
    assert int_10_00["forecast_error_mw"] == 500.0
    assert int_10_00["absolute_error_mw"] == 500.0
    assert int_10_00["percentage_error"] == 5.0

    int_10_30 = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-01T10:30:00Z"][0]
    assert int_10_30["is_matched"] is True
    assert int_10_30["actual_generation_mw"] == 10200.0
    assert int_10_30["forecast_generation_mw"] == 10500.0
    assert int_10_30["forecast_error_mw"] == 300.0


@pytest.mark.asyncio
async def test_comparison_valid_multi_day_request(isolated_client_and_db):
    """GET /api/comparison for 2 days returns 96 intervals and per-date cutoff map."""
    client, Session = isolated_client_and_db

    ts_jan1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    ts_jan2 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_actual(session, ts_jan1, 11000.0)
        await _add_actual(session, ts_jan2, 12000.0)
        await _add_forecast(session, ts_jan1, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 11500.0)
        await _add_forecast(session, ts_jan2, datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC_TZ), 12500.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-02&decision_cutoff=11:00")
    assert resp.status_code == 200
    data = resp.json()

    assert data["date_range_start"] == "2026-01-01"
    assert data["date_range_end"] == "2026-01-02"
    assert data["expected_interval_count"] == 96
    assert data["actual_interval_count"] == 2
    assert data["unique_hourly_forecast_count"] == 2
    assert data["matched_interval_count"] == 2
    assert len(data["intervals"]) == 96

    assert data["decision_cutoffs_by_date"] == {
        "2026-01-01": "2025-12-31T11:00:00Z",
        "2026-01-02": "2026-01-01T11:00:00Z",
    }


@pytest.mark.asyncio
async def test_comparison_per_delivery_date_cutoff_behavior(isolated_client_and_db):
    """Cutoff applied separately: publication at 2025-12-31 11:30 is post-cutoff for Jan 1, but ex-ante for Jan 2."""
    client, Session = isolated_client_and_db

    ts_jan1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    ts_jan2 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC_TZ)
    # Publication timestamp: 11:30 on Dec 31
    pub_ts = datetime(2025, 12, 31, 11, 30, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_actual(session, ts_jan1, 10000.0)
        await _add_actual(session, ts_jan2, 12000.0)
        await _add_forecast(session, ts_jan1, pub_ts, 11000.0)
        await _add_forecast(session, ts_jan2, pub_ts, 12500.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-02&decision_cutoff=11:00")
    assert resp.status_code == 200
    data = resp.json()

    # Jan 1: forecast was published after 11:00 cutoff -> rejected!
    row_jan1 = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-01T12:00:00Z"][0]
    assert row_jan1["is_forecast_available"] is False
    assert row_jan1["is_matched"] is False

    # Jan 2: cutoff is 2026-01-01 11:00; pub_ts 2025-12-31 11:30 is well before -> accepted!
    row_jan2 = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-02T12:00:00Z"][0]
    assert row_jan2["is_forecast_available"] is True
    assert row_jan2["is_matched"] is True
    assert row_jan2["forecast_error_mw"] == 500.0


@pytest.mark.asyncio
async def test_comparison_exact_cutoff_boundary(isolated_client_and_db):
    """Forecast published exactly at D-1 11:00:00 is eligible."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 15, 0, 0, tzinfo=UTC_TZ)
    exact_cutoff_pub = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_actual(session, deliv_ts, 10000.0)
        await _add_forecast(session, deliv_ts, exact_cutoff_pub, 10800.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01&decision_cutoff=11:00")
    assert resp.status_code == 200
    data = resp.json()

    row = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-01T15:00:00Z"][0]
    assert row["is_forecast_available"] is True
    assert row["is_matched"] is True
    assert row["forecast_generation_mw"] == 10800.0


@pytest.mark.asyncio
async def test_comparison_forecast_after_cutoff_excluded(isolated_client_and_db):
    """Forecast published at D-1 11:00:01 is excluded."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 15, 0, 0, tzinfo=UTC_TZ)
    after_cutoff_pub = datetime(2025, 12, 31, 11, 0, 1, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_actual(session, deliv_ts, 10000.0)
        await _add_forecast(session, deliv_ts, after_cutoff_pub, 10800.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01&decision_cutoff=11:00")
    assert resp.status_code == 200
    data = resp.json()

    row = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-01T15:00:00Z"][0]
    assert row["is_forecast_available"] is False
    assert row["is_matched"] is False
    assert row["forecast_error_mw"] is None


@pytest.mark.asyncio
async def test_comparison_missing_actual_retained_as_none(isolated_client_and_db):
    """Missing actual is retained as None, never coerced to 0."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    pub_ts = datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_forecast(session, deliv_ts, pub_ts, 12000.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()

    row = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-01T10:00:00Z"][0]
    assert row["is_actual_available"] is False
    assert row["actual_generation_mw"] is None
    assert row["is_matched"] is False
    assert row["forecast_error_mw"] is None
    assert data["missing_actual_intervals"] == 48


@pytest.mark.asyncio
async def test_comparison_missing_forecast_retained_as_none(isolated_client_and_db):
    """Missing forecast is retained as None, never coerced to 0."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_actual(session, deliv_ts, 11000.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()

    row = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-01T10:00:00Z"][0]
    assert row["is_forecast_available"] is False
    assert row["forecast_generation_mw"] is None
    assert row["is_matched"] is False
    assert row["forecast_error_mw"] is None
    assert data["missing_forecast_intervals"] == 48


@pytest.mark.asyncio
async def test_comparison_multiple_vintages_selects_latest_before_cutoff(isolated_client_and_db):
    """When multiple vintages exist, the latest published at or before cutoff is selected."""
    client, Session = isolated_client_and_db

    deliv_ts = datetime(2026, 1, 1, 16, 0, 0, tzinfo=UTC_TZ)
    pub_06 = datetime(2025, 12, 31, 6, 0, 0, tzinfo=UTC_TZ)
    pub_10 = datetime(2025, 12, 31, 10, 0, 0, tzinfo=UTC_TZ)
    pub_12 = datetime(2025, 12, 31, 12, 0, 0, tzinfo=UTC_TZ)  # after 11:00 cutoff

    async with Session() as session:
        await _add_actual(session, deliv_ts, 10000.0)
        await _add_forecast(session, deliv_ts, pub_06, 9000.0)
        await _add_forecast(session, deliv_ts, pub_10, 10500.0)
        await _add_forecast(session, deliv_ts, pub_12, 12000.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01&decision_cutoff=11:00")
    assert resp.status_code == 200
    data = resp.json()

    row = [i for i in data["intervals"] if i["delivery_timestamp"] == "2026-01-01T16:00:00Z"][0]
    assert row["forecast_publish_timestamp"] == "2025-12-31T10:00:00Z"
    assert row["forecast_generation_mw"] == 10500.0
    assert row["forecast_error_mw"] == 500.0


@pytest.mark.asyncio
async def test_comparison_resolution_bridge_and_unique_counts(isolated_client_and_db):
    """One hourly forecast covers two half-hourly actuals; unique forecast count is 1, covered is 2."""
    client, Session = isolated_client_and_db

    ts_10_00 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    ts_10_30 = datetime(2026, 1, 1, 10, 30, 0, tzinfo=UTC_TZ)
    fc_10_00 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)

    async with Session() as session:
        await _add_actual(session, ts_10_00, 10000.0)
        await _add_actual(session, ts_10_30, 10500.0)
        await _add_forecast(session, fc_10_00, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 11000.0)

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()

    assert data["unique_hourly_forecast_count"] == 1
    assert data["forecast_covered_interval_count"] == 2
    assert data["matched_interval_count"] == 2
    assert data["actual_interval_count"] == 2


@pytest.mark.asyncio
async def test_comparison_invalid_inputs_422(isolated_client_and_db):
    """Invalid date range (start > end) or invalid cutoff returns 422."""
    client, _ = isolated_client_and_db

    # start > end
    resp1 = await client.get("/api/comparison?start_date=2026-01-05&end_date=2026-01-01")
    assert resp1.status_code == 422

    # cutoff out of range
    resp2 = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01&decision_cutoff=25:00")
    assert resp2.status_code == 422

    # cutoff malformed string
    resp3 = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01&decision_cutoff=invalid")
    assert resp3.status_code == 422


@pytest.mark.asyncio
async def test_comparison_empty_database(isolated_client_and_db):
    """Empty database returns 200, 48 intervals all with None data, matched_interval_count=0."""
    client, _ = isolated_client_and_db

    resp = await client.get("/api/comparison?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()

    assert data["expected_interval_count"] == 48
    assert data["actual_interval_count"] == 0
    assert data["unique_hourly_forecast_count"] == 0
    assert data["matched_interval_count"] == 0
    assert data["missing_actual_intervals"] == 48
    assert data["missing_forecast_intervals"] == 48
    assert len(data["intervals"]) == 48
    assert all(i["is_matched"] is False for i in data["intervals"])
    assert all(i["actual_generation_mw"] is None for i in data["intervals"])
    assert all(i["forecast_generation_mw"] is None for i in data["intervals"])
