import json
from datetime import date, datetime
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.app.core.timezone import UTC_TZ
from backend.app.models.actual import ActualGeneration
from backend.app.models.forecast import ForecastGeneration
from backend.app.models.audit import IngestionLog
from backend.app.core.database import Base
from backend.app.schemas.elexon import FuelhhWindRecord, WindforForecastRecord
from backend.app.services.ingestion_service import IngestionService

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest_asyncio.fixture
async def test_db():
    """In-memory SQLite async test database fixture."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )

    async with TestSessionLocal() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_actual_record_persistence(test_db: AsyncSession):
    """Verify persisting FuelhhWindRecord preserves native 30-min settlement period attributes."""
    service = IngestionService(db=test_db)
    records = [
        FuelhhWindRecord(
            start_time="2026-01-01T00:00:00Z",
            settlement_date="2026-01-01",
            settlement_period=1,
            generation_mw=14250.0,
            fuel_type="WIND",
            dataset="FUELHH"
        ),
        FuelhhWindRecord(
            start_time="2026-01-01T00:30:00Z",
            settlement_date="2026-01-01",
            settlement_period=2,
            generation_mw=14800.5,
            fuel_type="WIND",
            dataset="FUELHH"
        )
    ]

    result = await service.ingest_actual_wind_records(records)
    assert result.records_retrieved == 2
    assert result.records_inserted == 2
    assert result.records_skipped_duplicate == 0

    # Query DB
    rows = (await test_db.execute(select(ActualGeneration).order_by(ActualGeneration.delivery_timestamp))).scalars().all()
    assert len(rows) == 2
    assert rows[0].settlement_period == 1
    assert rows[0].generation_mw == 14250.0
    assert rows[0].delivery_date == date(2026, 1, 1)
    assert rows[1].settlement_period == 2
    assert rows[1].generation_mw == 14800.5


@pytest.mark.asyncio
async def test_forecast_vintage_persistence(test_db: AsyncSession):
    """Verify multiple publication vintages for the same delivery interval are preserved without overwriting."""
    service = IngestionService(db=test_db)
    target_delivery = "2026-01-01T12:00:00Z"
    
    # 3 distinct publication runs for the same delivery interval
    records = [
        WindforForecastRecord(
            start_time=target_delivery,
            publish_time="2025-12-31T04:30:00Z",
            generation_mw=14100.0
        ),
        WindforForecastRecord(
            start_time=target_delivery,
            publish_time="2025-12-31T07:30:00Z",
            generation_mw=14600.0
        ),
        WindforForecastRecord(
            start_time=target_delivery,
            publish_time="2025-12-31T09:30:00Z",
            generation_mw=15200.0
        ),
    ]

    result = await service.ingest_forecast_records(records)
    assert result.records_retrieved == 3
    assert result.records_inserted == 3
    assert result.records_skipped_duplicate == 0

    # Query DB: All 3 vintages must exist
    rows = (await test_db.execute(select(ForecastGeneration).order_by(ForecastGeneration.publish_timestamp))).scalars().all()
    assert len(rows) == 3
    assert rows[0].publish_timestamp == datetime(2025, 12, 31, 4, 30, 0, tzinfo=UTC_TZ)
    assert rows[0].generation_mw == 14100.0
    assert rows[1].publish_timestamp == datetime(2025, 12, 31, 7, 30, 0, tzinfo=UTC_TZ)
    assert rows[1].generation_mw == 14600.0
    assert rows[2].publish_timestamp == datetime(2025, 12, 31, 9, 30, 0, tzinfo=UTC_TZ)
    assert rows[2].generation_mw == 15200.0


@pytest.mark.asyncio
async def test_duplicate_ingestion_idempotency(test_db: AsyncSession):
    """Verify running ingestion multiple times is idempotent and skips duplicates safely."""
    service = IngestionService(db=test_db)
    records = [
        FuelhhWindRecord(
            start_time="2026-01-01T01:00:00Z",
            settlement_date="2026-01-01",
            settlement_period=3,
            generation_mw=13000.0,
            fuel_type="WIND"
        )
    ]

    # First ingestion
    res1 = await service.ingest_actual_wind_records(records)
    assert res1.records_inserted == 1
    assert res1.records_skipped_duplicate == 0

    # Second ingestion with same record
    res2 = await service.ingest_actual_wind_records(records)
    assert res2.records_inserted == 0
    assert res2.records_skipped_duplicate == 1

    # Total in DB should still be 1
    count = (await test_db.execute(select(func.count(ActualGeneration.id)))).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_unique_constraint_violation(test_db: AsyncSession):
    """Verify unique constraint raises IntegrityError if duplicate entity is forced directly."""
    entity1 = ActualGeneration(
        delivery_timestamp=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ),
        delivery_date=date(2026, 1, 1),
        settlement_period=1,
        generation_mw=12000.0,
        fuel_type="WIND",
        source="ELEXON_FUELHH"
    )
    test_db.add(entity1)
    await test_db.commit()

    entity2 = ActualGeneration(
        delivery_timestamp=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ),
        delivery_date=date(2026, 1, 1),
        settlement_period=1,
        generation_mw=12500.0,
        fuel_type="WIND",
        source="ELEXON_FUELHH"
    )
    test_db.add(entity2)
    with pytest.raises(IntegrityError):
        await test_db.commit()


@pytest.mark.asyncio
async def test_january_coverage_calculation(test_db: AsyncSession):
    """Verify CoverageReport calculation accounts for 1488 expected actuals and 744 expected hourly forecasts."""
    service = IngestionService(db=test_db)

    # Ingest 48 actual intervals for Jan 1
    actuals = [
        FuelhhWindRecord(
            start_time=f"2026-01-01T{h:02d}:{m:02d}:00Z",
            settlement_date="2026-01-01",
            settlement_period=(h * 2 + (1 if m == 0 else 2)),
            generation_mw=15000.0,
            fuel_type="WIND"
        )
        for h in range(24)
        for m in (0, 30)
    ]
    assert len(actuals) == 48
    await service.ingest_actual_wind_records(actuals)

    # Ingest 24 hourly forecasts for Jan 1 (with 2 vintages per interval = 48 records)
    forecasts = []
    for h in range(24):
        for pub_h in [4, 7]:
            forecasts.append(
                WindforForecastRecord(
                    start_time=f"2026-01-01T{h:02d}:00:00Z",
                    publish_time=f"2025-12-31T{pub_h:02d}:30:00Z",
                    generation_mw=14500.0
                )
            )
    assert len(forecasts) == 48
    await service.ingest_forecast_records(forecasts)

    # Calculate coverage
    coverage = await service.get_january_coverage_report()
    assert coverage.expected_actual_intervals == 1488
    assert coverage.stored_actual_intervals == 48
    assert coverage.missing_actual_intervals == 1440
    assert coverage.actual_coverage_percent == 3.23

    assert coverage.expected_hourly_forecast_intervals == 744
    assert coverage.stored_forecast_vintages_count == 48
    assert coverage.unique_forecast_delivery_intervals == 24
    assert coverage.missing_forecast_delivery_intervals == 720
    assert coverage.forecast_interval_coverage_percent == 3.23


@pytest.mark.asyncio
async def test_fixture_offline_ingestion(test_db: AsyncSession):
    """Verify ingestion of sample offline fixtures into database."""
    service = IngestionService(db=test_db)

    with open(FIXTURES_DIR / "fuelhh_sample.json", "r", encoding="utf-8") as f:
        raw_fuel = json.load(f)
    wind_actuals = [
        FuelhhWindRecord(
            start_time=r["startTime"],
            settlement_date=r["settlementDate"],
            settlement_period=r["settlementPeriod"],
            generation_mw=r["generation"],
            fuel_type=r["fuelType"]
        )
        for r in raw_fuel if r.get("fuelType") == "WIND"
    ]
    act_res = await service.ingest_actual_wind_records(wind_actuals)
    assert act_res.records_inserted == 3

    with open(FIXTURES_DIR / "windfor_sample.json", "r", encoding="utf-8") as f:
        raw_wind = json.load(f)
    wind_forecasts = [
        WindforForecastRecord(
            start_time=r["startTime"],
            publish_time=r["publishTime"],
            generation_mw=r["generation"]
        )
        for r in raw_wind
    ]
    fc_res = await service.ingest_forecast_records(wind_forecasts)
    assert fc_res.records_inserted == 5
