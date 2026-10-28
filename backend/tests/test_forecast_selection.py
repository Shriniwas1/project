"""Phase 4 tests: Forecast Selection Engine.

Tests enforce the strict day-ahead vintage selection rules:
- The latest forecast published AT OR BEFORE the decision cutoff is selected.
- Forecasts published AFTER the cutoff are never selected (no look-ahead bias).
- Intervals with no eligible forecast are marked is_forecast_available=False.
- The 30-min actual → 1-hour WINDFOR resolution bridge works correctly.
- ComparisonSummarySchema counts match, missing, and unmatched intervals.
- Error metrics (forecast_error, absolute_error, percentage_error) are correct.
- MAPE exclusion: percentage_error is None when actual_generation == 0.
"""

from datetime import date, datetime
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.timezone import UTC_TZ, ensure_utc
from backend.app.core.database import Base
from backend.app.models.actual import ActualGeneration
from backend.app.models.forecast import ForecastGeneration
from backend.app.services.forecast_selection_service import ForecastSelectionService, _floor_to_hour
from backend.app.schemas.comparison import SelectedForecastSchema, ComparisonIntervalSchema


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db():
    """In-memory SQLite async database for Phase 4 tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


async def _add_actual(db, delivery_ts: datetime, generation_mw: float) -> ActualGeneration:
    """Helper to insert an ActualGeneration record."""
    from backend.app.core.timezone import get_delivery_date_for_interval, calculate_settlement_period
    row = ActualGeneration(
        delivery_timestamp=delivery_ts,
        delivery_date=get_delivery_date_for_interval(delivery_ts),
        settlement_period=calculate_settlement_period(delivery_ts),
        generation_mw=generation_mw,
        fuel_type="WIND",
        source="ELEXON_FUELHH",
    )
    db.add(row)
    await db.commit()
    return row


async def _add_forecast(db, delivery_ts: datetime, publish_ts: datetime, generation_mw: float) -> ForecastGeneration:
    """Helper to insert a ForecastGeneration record."""
    from backend.app.core.timezone import get_delivery_date_for_interval
    row = ForecastGeneration(
        delivery_timestamp=delivery_ts,
        delivery_date=get_delivery_date_for_interval(delivery_ts),
        publish_timestamp=publish_ts,
        generation_mw=generation_mw,
        source="ELEXON_WINDFOR",
        is_ex_ante=True,
    )
    db.add(row)
    await db.commit()
    return row


# ---------------------------------------------------------------------------
# Unit: _floor_to_hour helper
# ---------------------------------------------------------------------------

def test_floor_to_hour_on_boundary():
    """A timestamp already on the hour should not change."""
    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    assert _floor_to_hour(dt) == dt


def test_floor_to_hour_half_past():
    """A timestamp at XX:30 should floor to XX:00."""
    dt = datetime(2026, 1, 1, 12, 30, 0, tzinfo=UTC_TZ)
    expected = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    assert _floor_to_hour(dt) == expected


def test_floor_to_hour_preserves_tzinfo():
    """_floor_to_hour must preserve the tzinfo of the input."""
    dt = datetime(2026, 1, 1, 9, 30, 0, tzinfo=UTC_TZ)
    result = _floor_to_hour(dt)
    assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# Core selection: select_forecast_for_interval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_latest_eligible_forecast(test_db):
    """Given multiple vintages all before the cutoff, the latest is selected."""
    delivery_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    cutoff_utc = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)

    # Add 3 vintages for the same delivery interval
    await _add_forecast(test_db, delivery_ts, datetime(2025, 12, 31, 4, 30, 0, tzinfo=UTC_TZ), 14000.0)
    await _add_forecast(test_db, delivery_ts, datetime(2025, 12, 31, 7, 30, 0, tzinfo=UTC_TZ), 14500.0)
    await _add_forecast(test_db, delivery_ts, datetime(2025, 12, 31, 10, 30, 0, tzinfo=UTC_TZ), 15000.0)

    svc = ForecastSelectionService(db=test_db)
    selected = await svc.select_forecast_for_interval(delivery_ts, cutoff_utc)

    assert selected is not None
    # Should select the 10:30 vintage (latest before 11:00 cutoff)
    pub = ensure_utc(selected.publish_timestamp)
    assert pub == datetime(2025, 12, 31, 10, 30, 0, tzinfo=UTC_TZ)
    assert selected.generation_mw == 15000.0


@pytest.mark.asyncio
async def test_reject_forecast_published_after_cutoff(test_db):
    """Forecasts published after the cutoff must never be selected."""
    delivery_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    cutoff_utc = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)

    # Only add a forecast published AFTER the cutoff (14:00)
    await _add_forecast(test_db, delivery_ts, datetime(2025, 12, 31, 14, 0, 0, tzinfo=UTC_TZ), 15500.0)

    svc = ForecastSelectionService(db=test_db)
    selected = await svc.select_forecast_for_interval(delivery_ts, cutoff_utc)

    assert selected is None, "Forecast after cutoff must NOT be selected"


@pytest.mark.asyncio
async def test_select_forecast_exactly_at_cutoff(test_db):
    """A forecast published EXACTLY at the decision cutoff must be eligible (<=)."""
    delivery_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    cutoff_utc = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)

    await _add_forecast(test_db, delivery_ts, cutoff_utc, 15200.0)  # Exactly at cutoff

    svc = ForecastSelectionService(db=test_db)
    selected = await svc.select_forecast_for_interval(delivery_ts, cutoff_utc)

    assert selected is not None
    assert ensure_utc(selected.publish_timestamp) == cutoff_utc
    assert selected.generation_mw == 15200.0


@pytest.mark.asyncio
async def test_select_forecast_no_forecasts_returns_none(test_db):
    """When there are no forecasts at all, returns None."""
    delivery_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    cutoff_utc = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)

    svc = ForecastSelectionService(db=test_db)
    selected = await svc.select_forecast_for_interval(delivery_ts, cutoff_utc)

    assert selected is None


@pytest.mark.asyncio
async def test_resolution_bridge_30min_actual_maps_to_1hour_forecast(test_db):
    """A 30-min actual at 12:30 must match the forecast at 12:00 (floor to hour)."""
    delivery_12_00 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    delivery_12_30 = datetime(2026, 1, 1, 12, 30, 0, tzinfo=UTC_TZ)
    cutoff_utc = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)

    # Only a forecast at 12:00 (no 12:30 forecast, as WINDFOR is 1-hour resolution)
    await _add_forecast(test_db, delivery_12_00, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 14800.0)

    svc = ForecastSelectionService(db=test_db)

    # Selecting for the 12:30 actual should find the 12:00 forecast
    selected_for_12_30 = await svc.select_forecast_for_interval(delivery_12_30, cutoff_utc)
    selected_for_12_00 = await svc.select_forecast_for_interval(delivery_12_00, cutoff_utc)

    assert selected_for_12_30 is not None, "12:30 actual must map to 12:00 forecast"
    assert selected_for_12_00 is not None
    assert selected_for_12_30.id == selected_for_12_00.id, "Both should select the same forecast row"
    assert selected_for_12_30.generation_mw == 14800.0


# ---------------------------------------------------------------------------
# get_selected_forecasts_for_date
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_selected_forecasts_returns_48_intervals(test_db):
    """get_selected_forecasts_for_date must return exactly 48 intervals for a standard day."""
    delivery_date = date(2026, 1, 1)
    svc = ForecastSelectionService(db=test_db)

    results = await svc.get_selected_forecasts_for_date(delivery_date, "11:00")

    assert len(results) == 48, f"Expected 48 intervals, got {len(results)}"


@pytest.mark.asyncio
async def test_get_selected_forecasts_marks_unavailable_when_no_data(test_db):
    """All intervals must be marked is_forecast_available=False when no forecasts are stored."""
    delivery_date = date(2026, 1, 1)
    svc = ForecastSelectionService(db=test_db)

    results = await svc.get_selected_forecasts_for_date(delivery_date, "11:00")

    assert all(not r.is_forecast_available for r in results)
    assert all(r.forecast_generation_mw is None for r in results)


@pytest.mark.asyncio
async def test_get_selected_forecasts_interval_ordering(test_db):
    """Selected forecast intervals must be ordered chronologically."""
    delivery_date = date(2026, 1, 1)
    svc = ForecastSelectionService(db=test_db)

    results = await svc.get_selected_forecasts_for_date(delivery_date, "11:00")

    timestamps = [r.delivery_timestamp for r in results]
    assert timestamps == sorted(timestamps), "Intervals must be in ascending time order"


@pytest.mark.asyncio
async def test_get_selected_forecasts_correct_cutoff_in_response(test_db):
    """The decision_cutoff_utc in each result must match the configured cutoff."""
    delivery_date = date(2026, 1, 1)
    svc = ForecastSelectionService(db=test_db)

    results = await svc.get_selected_forecasts_for_date(delivery_date, "11:00")

    # For Jan 2026 (GMT), 11:00 London == 11:00 UTC
    expected_cutoff = "2025-12-31T11:00:00Z"
    assert all(r.decision_cutoff_utc == expected_cutoff for r in results)


@pytest.mark.asyncio
async def test_get_selected_forecasts_selects_correct_vintage(test_db):
    """When multiple vintages exist, each interval gets the latest eligible one."""
    delivery_date = date(2026, 1, 1)
    cutoff_str = "11:00"

    # Add two vintages for the 06:00 delivery interval
    delivery_06_00 = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC_TZ)
    await _add_forecast(test_db, delivery_06_00, datetime(2025, 12, 31, 5, 0, 0, tzinfo=UTC_TZ), 13000.0)
    await _add_forecast(test_db, delivery_06_00, datetime(2025, 12, 31, 10, 0, 0, tzinfo=UTC_TZ), 13500.0)  # Latest eligible
    await _add_forecast(test_db, delivery_06_00, datetime(2025, 12, 31, 13, 0, 0, tzinfo=UTC_TZ), 14000.0)  # After cutoff

    svc = ForecastSelectionService(db=test_db)
    results = await svc.get_selected_forecasts_for_date(delivery_date, cutoff_str)

    # The 06:00 and 06:30 intervals should both select the 10:00 vintage (latest eligible)
    interval_06_00 = next(r for r in results if r.delivery_timestamp == "2026-01-01T06:00:00Z")
    interval_06_30 = next(r for r in results if r.delivery_timestamp == "2026-01-01T06:30:00Z")

    assert interval_06_00.is_forecast_available is True
    assert interval_06_00.forecast_generation_mw == 13500.0
    assert interval_06_00.forecast_publish_timestamp == "2025-12-31T10:00:00Z"

    assert interval_06_30.is_forecast_available is True
    assert interval_06_30.forecast_generation_mw == 13500.0, "12:30 must share same 1-hour forecast"


# ---------------------------------------------------------------------------
# build_comparison_for_date — full integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comparison_matched_interval_computes_error(test_db):
    """A matched interval (both actual and forecast available) must compute all error fields."""
    delivery_date = date(2026, 1, 1)

    # Add actual at 12:00
    await _add_actual(test_db, datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ), 14000.0)
    # Add eligible forecast
    await _add_forecast(
        test_db,
        datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ),
        datetime(2025, 12, 31, 9, 0, 0, tzinfo=UTC_TZ),
        14500.0,
    )

    svc = ForecastSelectionService(db=test_db)
    summary = await svc.build_comparison_for_date(delivery_date, "11:00")

    interval_12_00 = next(
        i for i in summary.intervals if i.delivery_timestamp == "2026-01-01T12:00:00Z"
    )
    assert interval_12_00.is_matched is True
    assert interval_12_00.actual_generation_mw == 14000.0
    assert interval_12_00.forecast_generation_mw == 14500.0
    assert interval_12_00.forecast_error_mw == pytest.approx(500.0)
    assert interval_12_00.absolute_error_mw == pytest.approx(500.0)
    assert interval_12_00.percentage_error == pytest.approx(500.0 / 14000.0 * 100.0, rel=1e-3)


@pytest.mark.asyncio
async def test_comparison_missing_forecast_interval(test_db):
    """When no eligible forecast exists, interval must be unmatched and not compute errors."""
    delivery_date = date(2026, 1, 1)

    # Add actual only
    await _add_actual(test_db, datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC_TZ), 13000.0)

    svc = ForecastSelectionService(db=test_db)
    summary = await svc.build_comparison_for_date(delivery_date, "11:00")

    interval_08_00 = next(i for i in summary.intervals if i.delivery_timestamp == "2026-01-01T08:00:00Z")
    assert interval_08_00.is_actual_available is True
    assert interval_08_00.is_forecast_available is False
    assert interval_08_00.is_matched is False
    assert interval_08_00.forecast_error_mw is None
    assert interval_08_00.absolute_error_mw is None
    assert interval_08_00.percentage_error is None


@pytest.mark.asyncio
async def test_comparison_missing_actual_interval(test_db):
    """When no actual exists, interval must be unmatched even if forecast is available."""
    delivery_date = date(2026, 1, 1)

    # Add forecast only (no actual)
    await _add_forecast(
        test_db,
        datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ),
        datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ),
        14200.0,
    )

    svc = ForecastSelectionService(db=test_db)
    summary = await svc.build_comparison_for_date(delivery_date, "11:00")

    interval_10_00 = next(i for i in summary.intervals if i.delivery_timestamp == "2026-01-01T10:00:00Z")
    assert interval_10_00.is_actual_available is False
    assert interval_10_00.is_forecast_available is True
    assert interval_10_00.is_matched is False
    assert interval_10_00.forecast_error_mw is None


@pytest.mark.asyncio
async def test_comparison_zero_actual_excludes_percentage_error(test_db):
    """When actual == 0 MW, percentage_error must be None (excluded from MAPE), not division-by-zero."""
    delivery_date = date(2026, 1, 1)

    await _add_actual(test_db, datetime(2026, 1, 1, 4, 0, 0, tzinfo=UTC_TZ), 0.0)
    await _add_forecast(
        test_db,
        datetime(2026, 1, 1, 4, 0, 0, tzinfo=UTC_TZ),
        datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ),
        500.0,
    )

    svc = ForecastSelectionService(db=test_db)
    summary = await svc.build_comparison_for_date(delivery_date, "11:00")

    interval_04_00 = next(i for i in summary.intervals if i.delivery_timestamp == "2026-01-01T04:00:00Z")
    assert interval_04_00.is_matched is True
    assert interval_04_00.forecast_error_mw == pytest.approx(500.0)
    assert interval_04_00.absolute_error_mw == pytest.approx(500.0)
    assert interval_04_00.percentage_error is None, "percentage_error must be None when actual == 0"


@pytest.mark.asyncio
async def test_comparison_negative_forecast_error_underforecast(test_db):
    """A forecast below actual must produce a negative forecast_error (underforecast)."""
    delivery_date = date(2026, 1, 1)

    await _add_actual(test_db, datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ), 15000.0)
    await _add_forecast(
        test_db,
        datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ),
        datetime(2025, 12, 31, 9, 0, 0, tzinfo=UTC_TZ),
        13000.0,
    )

    svc = ForecastSelectionService(db=test_db)
    summary = await svc.build_comparison_for_date(delivery_date, "11:00")

    interval = next(i for i in summary.intervals if i.delivery_timestamp == "2026-01-01T14:00:00Z")
    assert interval.forecast_error_mw == pytest.approx(-2000.0)
    assert interval.absolute_error_mw == pytest.approx(2000.0)
    assert interval.percentage_error == pytest.approx(-2000.0 / 15000.0 * 100.0, rel=1e-3)


@pytest.mark.asyncio
async def test_comparison_summary_counts_correct(test_db):
    """ComparisonSummarySchema must report correct matched / missing counts.

    Setup: 2 actuals at 00:00 and 00:30, 1 forecast at 00:00 (1-hour resolution).
    The 00:30 actual shares the 00:00 forecast via _floor_to_hour resolution bridge.
    Result: Both 00:00 and 00:30 are matched (same forecast row, two separate comparisons).
    The remaining 46 of 48 30-min intervals have no actual and no forecast.
    """
    delivery_date = date(2026, 1, 1)

    await _add_actual(test_db, datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ), 12000.0)
    await _add_forecast(
        test_db,
        datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ),
        datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ),
        12200.0,
    )

    # 00:30 actual — maps to the same 00:00 forecast via floor_to_hour
    await _add_actual(test_db, datetime(2026, 1, 1, 0, 30, 0, tzinfo=UTC_TZ), 12100.0)

    svc = ForecastSelectionService(db=test_db)
    summary = await svc.build_comparison_for_date(delivery_date, "11:00")

    assert summary.total_intervals == 48
    # Both 00:00 and 00:30 are matched: same 1-hour forecast covers both 30-min actuals
    assert summary.matched_intervals == 2
    # 46 of 48 intervals have no eligible forecast selected (no forecast stored for them)
    assert summary.missing_forecast_intervals == 46
    # 46 of 48 intervals have no actual outturn stored
    assert summary.missing_actual_intervals == 46


@pytest.mark.asyncio
async def test_comparison_cutoff_time_in_response(test_db):
    """cutoff_time_local in the summary must equal the input cutoff_time_str."""
    delivery_date = date(2026, 1, 1)
    svc = ForecastSelectionService(db=test_db)
    summary = await svc.build_comparison_for_date(delivery_date, "09:30")

    assert summary.cutoff_time_local == "09:30"
    # For GMT, London 09:30 == UTC 09:30
    assert summary.decision_cutoff_utc == "2025-12-31T09:30:00Z"


# ---------------------------------------------------------------------------
# Forecast Vintages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_forecast_vintages_returns_all_for_date(test_db):
    """get_forecast_vintages_for_date must return all stored vintages for the delivery date."""
    delivery_date = date(2026, 1, 1)
    delivery_ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC_TZ)

    await _add_forecast(test_db, delivery_ts, datetime(2025, 12, 31, 4, 0, 0, tzinfo=UTC_TZ), 13000.0)
    await _add_forecast(test_db, delivery_ts, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 13500.0)
    await _add_forecast(test_db, delivery_ts, datetime(2025, 12, 31, 14, 0, 0, tzinfo=UTC_TZ), 14000.0)

    svc = ForecastSelectionService(db=test_db)
    vintages = await svc.get_forecast_vintages_for_date(delivery_date)

    assert len(vintages) == 3

    pub_times = [v.publish_timestamp for v in vintages]
    assert "2025-12-31T04:00:00Z" in pub_times
    assert "2025-12-31T08:00:00Z" in pub_times
    assert "2025-12-31T14:00:00Z" in pub_times


@pytest.mark.asyncio
async def test_get_forecast_vintages_empty_when_no_data(test_db):
    """get_forecast_vintages_for_date must return an empty list when no forecasts are stored."""
    svc = ForecastSelectionService(db=test_db)
    vintages = await svc.get_forecast_vintages_for_date(date(2026, 1, 15))
    assert vintages == []


@pytest.mark.asyncio
async def test_get_forecast_vintages_lead_time_calculation(test_db):
    """lead_time_hours must equal (delivery - publication) / 3600."""
    delivery_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    publish_ts = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)
    # Lead time = (2026-01-01T12:00 - 2025-12-31T11:00) = 25 hours
    await _add_forecast(test_db, delivery_ts, publish_ts, 14500.0)

    svc = ForecastSelectionService(db=test_db)
    vintages = await svc.get_forecast_vintages_for_date(date(2026, 1, 1))

    assert len(vintages) == 1
    assert vintages[0].lead_time_hours == pytest.approx(25.0)


@pytest.mark.asyncio
async def test_forecast_published_immediately_after_cutoff_is_ineligible(test_db):
    """A forecast published even 1 second after the cutoff must be strictly ineligible."""
    from datetime import timedelta
    delivery_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    cutoff_utc = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)
    post_cutoff_ts = cutoff_utc + timedelta(seconds=1)

    await _add_forecast(test_db, delivery_ts, post_cutoff_ts, 15000.0)

    svc = ForecastSelectionService(db=test_db)
    selected = await svc.select_forecast_for_interval(delivery_ts, cutoff_utc)
    assert selected is None, "Forecast published 1s after cutoff must NOT be selected"


@pytest.mark.asyncio
async def test_newer_ineligible_vintage_does_not_override_older_eligible_vintage(test_db):
    """A newer vintage published after the cutoff cannot override an earlier eligible vintage."""
    from datetime import timedelta
    delivery_ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ)
    cutoff_utc = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)

    # Eligible earlier vintage
    await _add_forecast(test_db, delivery_ts, cutoff_utc - timedelta(hours=2), 14000.0)
    # Ineligible newer vintage
    await _add_forecast(test_db, delivery_ts, cutoff_utc + timedelta(hours=1), 17000.0)

    svc = ForecastSelectionService(db=test_db)
    selected = await svc.select_forecast_for_interval(delivery_ts, cutoff_utc)
    assert selected is not None
    assert selected.generation_mw == 14000.0, "Eligible vintage must be selected; ineligible vintage ignored"


@pytest.mark.asyncio
async def test_missing_intermediate_delivery_hour_preserves_unavailability(test_db):
    """If an intermediate 1-hour forecast is missing, its corresponding settlement intervals are unavailable."""
    cutoff_utc = datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ)
    ts_08 = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC_TZ)
    ts_10 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    # 09:00 forecast is deliberately omitted

    await _add_forecast(test_db, ts_08, datetime(2025, 12, 31, 6, 0, 0, tzinfo=UTC_TZ), 12000.0)
    await _add_forecast(test_db, ts_10, datetime(2025, 12, 31, 6, 0, 0, tzinfo=UTC_TZ), 13000.0)

    svc = ForecastSelectionService(db=test_db)
    res_08_00 = await svc.select_forecast_for_interval(datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC_TZ), cutoff_utc)
    res_09_00 = await svc.select_forecast_for_interval(datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC_TZ), cutoff_utc)
    res_09_30 = await svc.select_forecast_for_interval(datetime(2026, 1, 1, 9, 30, 0, tzinfo=UTC_TZ), cutoff_utc)
    res_10_00 = await svc.select_forecast_for_interval(datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ), cutoff_utc)

    assert res_08_00 is not None
    assert res_09_00 is None, "Missing 09:00 hour must return None"
    assert res_09_30 is None, "Missing 09:30 half-hour must return None"
    assert res_10_00 is not None

