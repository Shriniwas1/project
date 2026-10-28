"""Phase 5 tests: Forecast Accuracy Calculations and Analytics API.

Coverage:
    Unit tests for _compute_metrics (pure function, no DB):
    - MAE calculation with known values
    - RMSE calculation with known values
    - Positive bias (overforecast)
    - Negative bias (underforecast)
    - MAPE calculation with known values
    - MAPE zero-actual exclusion
    - MAPE returns None when all actuals are zero
    - Empty matched set returns all-None metrics

    Integration tests using AccuracyService with in-memory DB:
    - Missing forecasts are excluded (not zeroed)
    - Missing actuals are excluded (not zeroed)
    - Single date accuracy
    - Multi-date range accuracy
    - Date range boundary conditions (inclusive both ends)
    - Cutoff propagation to selection engine
    - Hourly forecast matched to two half-hourly actuals
    - Coverage count correctness

    Regression tests for Phase 4 selection behavior:
    - Decision cutoff respected in accuracy pipeline
    - Post-cutoff forecast never enters accuracy calculation

    Analytics API tests:
    - Valid request returns 200 with AccuracyMetricsSchema
    - Invalid date range returns 422
    - Invalid cutoff format returns 422
    - Empty result set (no data) still returns valid schema
"""

import math
from datetime import date, datetime
from typing import List

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base
from backend.app.core.timezone import UTC_TZ, get_delivery_date_for_interval, calculate_settlement_period
from backend.app.models.actual import ActualGeneration
from backend.app.models.forecast import ForecastGeneration
from backend.app.schemas.comparison import ComparisonIntervalSchema
from backend.app.services.accuracy_service import AccuracyService, _compute_metrics


# ---------------------------------------------------------------------------
# Helpers — build minimal ComparisonIntervalSchema rows without DB
# ---------------------------------------------------------------------------

def _make_matched_row(
    delivery_ts: str,
    actual_mw: float,
    forecast_mw: float,
    delivery_date: str = "2026-01-01",
    cutoff_utc: str = "2025-12-31T11:00:00Z",
) -> ComparisonIntervalSchema:
    """Create a matched ComparisonIntervalSchema row with error fields pre-computed."""
    err = forecast_mw - actual_mw
    pct = (err / actual_mw * 100.0) if actual_mw != 0.0 else None
    return ComparisonIntervalSchema(
        delivery_timestamp=delivery_ts,
        delivery_date=delivery_date,
        settlement_period=1,
        decision_cutoff_utc=cutoff_utc,
        actual_generation_mw=actual_mw,
        is_actual_available=True,
        forecast_generation_mw=forecast_mw,
        forecast_publish_timestamp="2025-12-31T08:00:00Z",
        is_forecast_available=True,
        forecast_error_mw=err,
        absolute_error_mw=abs(err),
        percentage_error=pct,
        is_matched=True,
    )


def _make_unmatched_row(
    delivery_ts: str,
    actual_mw: float = None,
    forecast_mw: float = None,
) -> ComparisonIntervalSchema:
    """Create an unmatched row (missing actual or forecast)."""
    return ComparisonIntervalSchema(
        delivery_timestamp=delivery_ts,
        delivery_date="2026-01-01",
        settlement_period=1,
        decision_cutoff_utc="2025-12-31T11:00:00Z",
        actual_generation_mw=actual_mw,
        is_actual_available=actual_mw is not None,
        forecast_generation_mw=forecast_mw,
        forecast_publish_timestamp=None if forecast_mw is None else "2025-12-31T08:00:00Z",
        is_forecast_available=forecast_mw is not None,
        forecast_error_mw=None,
        absolute_error_mw=None,
        percentage_error=None,
        is_matched=False,
    )


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db():
    """In-memory SQLite async database for Phase 5 service tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


async def _add_actual(db, delivery_ts: datetime, generation_mw: float) -> ActualGeneration:
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


async def _add_forecast(
    db, delivery_ts: datetime, publish_ts: datetime, generation_mw: float
) -> ForecastGeneration:
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
# Unit tests: _compute_metrics (pure function, no DB required)
# ---------------------------------------------------------------------------

def test_compute_metrics_mae():
    """MAE = mean(|forecast - actual|)."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=10000.0, forecast_mw=10500.0),  # err = +500
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=10000.0, forecast_mw=9000.0),   # err = -1000
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert mae == pytest.approx((500.0 + 1000.0) / 2, rel=1e-6)


def test_compute_metrics_rmse():
    """RMSE = sqrt(mean((forecast - actual)²))."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=10000.0, forecast_mw=10300.0),  # err = +300
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=10000.0, forecast_mw=9600.0),   # err = -400
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    expected_rmse = math.sqrt((300.0**2 + 400.0**2) / 2)
    assert rmse == pytest.approx(expected_rmse, rel=1e-6)


def test_compute_metrics_positive_bias_overforecast():
    """Positive bias means forecast systematically exceeds actual."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=10000.0, forecast_mw=11000.0),  # err = +1000
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=10000.0, forecast_mw=10500.0),  # err = +500
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert bias == pytest.approx(750.0, rel=1e-6)
    assert bias > 0, "Positive bias must indicate overforecast"


def test_compute_metrics_negative_bias_underforecast():
    """Negative bias means forecast systematically underestimates actual."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=15000.0, forecast_mw=13000.0),  # err = -2000
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=15000.0, forecast_mw=14000.0),  # err = -1000
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert bias == pytest.approx(-1500.0, rel=1e-6)
    assert bias < 0, "Negative bias must indicate underforecast"


def test_compute_metrics_mape_calculation():
    """MAPE = mean(|error| / actual) × 100."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=10000.0, forecast_mw=10500.0),  # |err|/act = 0.05
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=8000.0, forecast_mw=8800.0),    # |err|/act = 0.10
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    expected_mape = ((0.05 + 0.10) / 2) * 100
    assert mape == pytest.approx(expected_mape, rel=1e-6)
    assert mape_n == 2
    assert zero_count == 0


def test_compute_metrics_mape_excludes_zero_actuals():
    """Intervals where actual == 0 are excluded from MAPE count and calculation."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=10000.0, forecast_mw=10500.0),  # |err|/act = 0.05
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=0.0, forecast_mw=500.0),         # excluded
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert zero_count == 1
    assert mape_n == 1
    # MAPE only over the non-zero row
    assert mape == pytest.approx(5.0, rel=1e-6)
    # MAE and RMSE still include the zero-actual row
    assert mae == pytest.approx((500.0 + 500.0) / 2, rel=1e-6)


def test_compute_metrics_mape_none_when_all_actuals_zero():
    """MAPE must be None when every matched interval has actual == 0."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=0.0, forecast_mw=500.0),
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=0.0, forecast_mw=300.0),
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert mape is None, "MAPE must be None when no eligible non-zero actual rows"
    assert zero_count == 2
    assert mape_n == 0
    # MAE and RMSE are still computed
    assert mae is not None
    assert rmse is not None


def test_compute_metrics_empty_returns_none():
    """Empty matched set must return None for all metrics and zero counts."""
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics([])
    assert mae is None
    assert rmse is None
    assert bias is None
    assert mape is None
    assert zero_count == 0
    assert mape_n == 0


def test_compute_metrics_single_interval():
    """Single matched interval produces well-defined metrics."""
    rows = [_make_matched_row("2026-01-01T06:00:00Z", actual_mw=12000.0, forecast_mw=12400.0)]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert mae == pytest.approx(400.0)
    assert rmse == pytest.approx(400.0)
    assert bias == pytest.approx(400.0)
    assert mape == pytest.approx(400.0 / 12000.0 * 100, rel=1e-6)


def test_compute_metrics_exact_forecast_zero_error():
    """When forecast == actual exactly, all metrics should be 0."""
    rows = [_make_matched_row("2026-01-01T06:00:00Z", actual_mw=14000.0, forecast_mw=14000.0)]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert mae == pytest.approx(0.0, abs=1e-9)
    assert rmse == pytest.approx(0.0, abs=1e-9)
    assert bias == pytest.approx(0.0, abs=1e-9)
    assert mape == pytest.approx(0.0, abs=1e-9)


def test_compute_metrics_constant_overforecasting():
    """Constant overforecasting: MAE == Bias == positive error constant."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=10000.0, forecast_mw=10500.0),  # +500
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=12000.0, forecast_mw=12500.0),  # +500
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert mae == pytest.approx(500.0)
    assert rmse == pytest.approx(500.0)
    assert bias == pytest.approx(500.0)
    assert zero_count == 0
    assert mape_n == 2


def test_compute_metrics_constant_underforecasting():
    """Constant underforecasting: MAE == abs(Bias), Bias is negative."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=10000.0, forecast_mw=9700.0),  # -300
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=12000.0, forecast_mw=11700.0), # -300
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert mae == pytest.approx(300.0)
    assert rmse == pytest.approx(300.0)
    assert bias == pytest.approx(-300.0)


def test_compute_metrics_mixture_positive_and_negative():
    """Balanced positive and negative errors cancel in Bias, but accumulate in MAE and RMSE."""
    rows = [
        _make_matched_row("2026-01-01T00:00:00Z", actual_mw=10000.0, forecast_mw=10400.0),  # +400
        _make_matched_row("2026-01-01T00:30:00Z", actual_mw=10000.0, forecast_mw=9600.0),   # -400
    ]
    mae, rmse, bias, mape, zero_count, mape_n = _compute_metrics(rows)
    assert mae == pytest.approx(400.0)
    assert rmse == pytest.approx(400.0)
    assert bias == pytest.approx(0.0, abs=1e-9)



# ---------------------------------------------------------------------------
# Integration tests: AccuracyService with in-memory DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accuracy_empty_db_returns_none_metrics(test_db):
    """With no data at all, all metrics must be None and coverage counts zero."""
    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1))

    assert result.matched_interval_count == 0
    assert result.mae_mw is None
    assert result.rmse_mw is None
    assert result.bias_mw is None
    assert result.mape_pct is None
    assert result.actual_interval_count == 0
    assert result.forecast_interval_count == 0
    assert result.expected_interval_count == 48  # 1 day × 48


@pytest.mark.asyncio
async def test_accuracy_missing_forecast_excluded_not_zeroed(test_db):
    """Intervals with actual but no eligible forecast must not be counted as matched."""
    delivery_ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, delivery_ts, 13000.0)
    # No forecast added

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1))

    assert result.actual_interval_count == 1
    assert result.forecast_interval_count == 0
    assert result.matched_interval_count == 0
    assert result.mae_mw is None, "MAE must be None — no matched interval"


@pytest.mark.asyncio
async def test_accuracy_missing_actual_excluded_not_zeroed(test_db):
    """Intervals with forecast but no actual must not be counted as matched."""
    delivery_ts = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC_TZ)
    await _add_forecast(test_db, delivery_ts, datetime(2025, 12, 31, 9, 0, 0, tzinfo=UTC_TZ), 14000.0)
    # No actual added

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1))

    assert result.actual_interval_count == 0
    assert result.forecast_interval_count >= 1  # both 08:00 and 08:30 find the forecast
    assert result.matched_interval_count == 0
    assert result.mae_mw is None


@pytest.mark.asyncio
async def test_accuracy_single_matched_interval(test_db):
    """Single matched interval: metrics equal per-interval error values."""
    delivery_ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, delivery_ts, 12000.0)
    await _add_forecast(
        test_db, delivery_ts, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 12600.0
    )

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")

    assert result.matched_interval_count == 1
    assert result.mae_mw == pytest.approx(600.0, rel=1e-4)
    assert result.rmse_mw == pytest.approx(600.0, rel=1e-4)
    assert result.bias_mw == pytest.approx(600.0, rel=1e-4)
    assert result.mape_pct == pytest.approx(600.0 / 12000.0 * 100, rel=1e-4)


@pytest.mark.asyncio
async def test_accuracy_hourly_forecast_matches_two_half_hourly_actuals(test_db):
    """
    One 1-hour WINDFOR forecast at 10:00 must be matched to both:
      - actual at 10:00 (SP 21)
      - actual at 10:30 (SP 22)
    This produces matched_interval_count == 2, not 1.
    Both comparison rows are independent for metric computation.
    """
    forecast_ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    actual_10_00 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    actual_10_30 = datetime(2026, 1, 1, 10, 30, 0, tzinfo=UTC_TZ)

    await _add_actual(test_db, actual_10_00, 14000.0)
    await _add_actual(test_db, actual_10_30, 14200.0)
    await _add_forecast(
        test_db, forecast_ts, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 14500.0
    )

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1))

    # Both actuals are matched to the same 1-hour forecast
    assert result.matched_interval_count == 2, (
        "One 1-hour forecast must produce two matched half-hourly comparison rows"
    )

    # MAE = mean(|14500-14000|, |14500-14200|) = mean(500, 300) = 400
    assert result.mae_mw == pytest.approx(400.0, rel=1e-4)
    # Bias = mean(500, 300) = 400 (overforecast for both)
    assert result.bias_mw == pytest.approx(400.0, rel=1e-4)


@pytest.mark.asyncio
async def test_accuracy_zero_actual_excluded_from_mape_only(test_db):
    """Zero-actual intervals count toward MAE/RMSE/Bias but not MAPE."""
    ts_zero = datetime(2026, 1, 1, 4, 0, 0, tzinfo=UTC_TZ)
    ts_nonzero = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC_TZ)

    await _add_actual(test_db, ts_zero, 0.0)
    await _add_forecast(test_db, ts_zero, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 400.0)

    await _add_actual(test_db, ts_nonzero, 12000.0)
    await _add_forecast(test_db, ts_nonzero, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 12600.0)

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1))

    assert result.zero_actual_excluded_count == 1
    assert result.mape_eligible_count == 1
    assert result.mape_pct == pytest.approx(600.0 / 12000.0 * 100, rel=1e-4)
    # MAE includes the zero-actual row: (|400-0| + |12600-12000|) / 2 = (400 + 600) / 2 = 500
    assert result.mae_mw == pytest.approx(500.0, rel=1e-4)


@pytest.mark.asyncio
async def test_accuracy_multi_date_range(test_db):
    """Metrics must aggregate correctly across multiple delivery dates."""
    # Jan 1: one matched interval with error 500
    ts_jan1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, ts_jan1, 10000.0)
    await _add_forecast(test_db, ts_jan1, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 10500.0)

    # Jan 2: one matched interval with error 1000
    ts_jan2 = datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, ts_jan2, 10000.0)
    await _add_forecast(test_db, ts_jan2, datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC_TZ), 11000.0)

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 2))

    assert result.matched_interval_count == 2
    assert result.expected_interval_count == 96  # 2 days × 48
    # MAE = (500 + 1000) / 2 = 750
    assert result.mae_mw == pytest.approx(750.0, rel=1e-4)


@pytest.mark.asyncio
async def test_accuracy_date_range_inclusive_boundaries(test_db):
    """Date range must be inclusive on both start_date and end_date."""
    # Add data only on Jan 3 (a boundary date)
    ts = datetime(2026, 1, 3, 12, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, ts, 11000.0)
    await _add_forecast(test_db, ts, datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC_TZ), 11200.0)

    svc = AccuracyService(db=test_db)

    # Range [Jan 1, Jan 3] must include Jan 3
    result_inclusive = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 3))
    # Range [Jan 1, Jan 2] must NOT include Jan 3
    result_exclusive = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 2))

    assert result_inclusive.matched_interval_count == 1
    assert result_exclusive.matched_interval_count == 0


@pytest.mark.asyncio
async def test_accuracy_cutoff_propagated_to_selection(test_db):
    """The cutoff_time_str must be respected: forecasts after the cutoff are not used."""
    delivery_ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, delivery_ts, 13000.0)

    # Forecast published at 10:00 — eligible under 11:00 cutoff
    await _add_forecast(
        test_db, delivery_ts, datetime(2025, 12, 31, 10, 0, 0, tzinfo=UTC_TZ), 13500.0
    )
    # Forecast published at 14:00 — NOT eligible under 11:00 cutoff
    await _add_forecast(
        test_db, delivery_ts, datetime(2025, 12, 31, 14, 0, 0, tzinfo=UTC_TZ), 15000.0
    )

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")

    # Must use the 10:00 forecast (error = 500), NOT the 14:00 forecast (error = 2000)
    assert result.matched_interval_count == 1
    assert result.mae_mw == pytest.approx(500.0, rel=1e-4)


@pytest.mark.asyncio
async def test_accuracy_post_cutoff_forecast_never_used(test_db):
    """If only a post-cutoff forecast exists, the interval must be unmatched (no zero substitution)."""
    delivery_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, delivery_ts, 14000.0)
    # Only a post-cutoff forecast
    await _add_forecast(
        test_db, delivery_ts, datetime(2025, 12, 31, 15, 0, 0, tzinfo=UTC_TZ), 14500.0
    )

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")

    assert result.matched_interval_count == 0
    assert result.mae_mw is None


@pytest.mark.asyncio
async def test_accuracy_coverage_counts(test_db):
    """Coverage counts must accurately reflect stored vs. expected intervals."""
    # 2 actuals, 1 forecast at 00:00 → both 00:00 and 00:30 find the same forecast
    await _add_actual(test_db, datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ), 12000.0)
    await _add_actual(test_db, datetime(2026, 1, 1, 0, 30, 0, tzinfo=UTC_TZ), 12100.0)
    await _add_forecast(
        test_db,
        datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ),
        datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ),
        12200.0,
    )

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1))

    assert result.expected_interval_count == 48
    assert result.actual_interval_count == 2
    # Both 00:00 and 00:30 have a forecast selected (same hourly forecast)
    assert result.forecast_interval_count == 2
    assert result.matched_interval_count == 2


@pytest.mark.asyncio
async def test_accuracy_cutoff_in_response(test_db):
    """Response must echo back the cutoff_time_local and computed decision_cutoff_utc."""
    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 5), date(2026, 1, 5), "09:30")

    assert result.cutoff_time_local == "09:30"
    # For GMT: Jan 5 D-1 is Jan 4, 09:30 London == 09:30 UTC
    assert result.decision_cutoff_utc == "2026-01-04T09:30:00Z"
    assert result.date_range_start == "2026-01-05"
    assert result.date_range_end == "2026-01-05"


@pytest.mark.asyncio
async def test_accuracy_resolution_fields_present(test_db):
    """Response must include resolution description fields."""
    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1))

    assert "30-minute" in result.actual_resolution
    assert "1-hour" in result.forecast_resolution or "WINDFOR" in result.forecast_resolution


# ---------------------------------------------------------------------------
# Analytics API endpoint tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def api_client():
    """Async HTTP test client for the FastAPI app with an isolated in-memory DB."""
    from backend.app.main import app
    from backend.app.core import database as db_module
    from backend.app.core.database import Base

    # Override get_db to use a fresh in-memory database for each API test
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def override_get_db():
        async with TestSession() as session:
            try:
                yield session
            finally:
                await session.close()

    from backend.app.core.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_analytics_endpoint_returns_200(api_client):
    """GET /api/analytics with valid params returns 200 and AccuracyMetricsSchema."""
    resp = await api_client.get("/api/analytics?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date_range_start"] == "2026-01-01"
    assert data["date_range_end"] == "2026-01-01"
    assert "matched_interval_count" in data
    assert "mae_mw" in data
    assert "rmse_mw" in data
    assert "bias_mw" in data
    assert "mape_pct" in data
    assert "expected_interval_count" in data
    assert "zero_actual_excluded_count" in data
    assert "mape_eligible_count" in data


@pytest.mark.asyncio
async def test_analytics_endpoint_no_data_returns_none_metrics(api_client):
    """With no data in DB, all metric fields must be null."""
    resp = await api_client.get("/api/analytics?start_date=2026-01-15&end_date=2026-01-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mae_mw"] is None
    assert data["rmse_mw"] is None
    assert data["bias_mw"] is None
    assert data["mape_pct"] is None
    assert data["matched_interval_count"] == 0


@pytest.mark.asyncio
async def test_analytics_endpoint_invalid_date_range(api_client):
    """end_date before start_date must return 422."""
    resp = await api_client.get("/api/analytics?start_date=2026-01-31&end_date=2026-01-01")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_analytics_endpoint_invalid_cutoff_format(api_client):
    """Malformed decision_cutoff must return 422."""
    resp = await api_client.get(
        "/api/analytics?start_date=2026-01-01&end_date=2026-01-01&decision_cutoff=11am"
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_analytics_endpoint_cutoff_out_of_range(api_client):
    """Cutoff with out-of-range hour/minute must return 422."""
    resp = await api_client.get(
        "/api/analytics?start_date=2026-01-01&end_date=2026-01-01&decision_cutoff=25:00"
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_analytics_endpoint_custom_cutoff_echoed(api_client):
    """Custom decision_cutoff must appear in the response."""
    resp = await api_client.get(
        "/api/analytics?start_date=2026-01-01&end_date=2026-01-02&decision_cutoff=09:30"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cutoff_time_local"] == "09:30"


@pytest.mark.asyncio
async def test_analytics_endpoint_default_cutoff_applied(api_client):
    """Without decision_cutoff param, the project default (11:00) must be used."""
    resp = await api_client.get("/api/analytics?start_date=2026-01-01&end_date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cutoff_time_local"] == "11:00"


@pytest.mark.asyncio
async def test_analytics_endpoint_multi_day_expected_count(api_client):
    """expected_interval_count must equal (number of days) × 48."""
    resp = await api_client.get("/api/analytics?start_date=2026-01-01&end_date=2026-01-07")
    assert resp.status_code == 200
    data = resp.json()
    assert data["expected_interval_count"] == 7 * 48  # 336


@pytest.mark.asyncio
async def test_analytics_endpoint_multi_day_cutoffs_by_date(api_client):
    """GET /api/analytics with multi-day range returns decision_cutoffs_by_date for each day."""
    resp = await api_client.get(
        "/api/analytics?start_date=2026-01-01&end_date=2026-01-02&decision_cutoff=11:00"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["date_boundary_type"] == "inclusive"
    assert data["cutoff_applied_per_delivery_date"] is True
    assert data["decision_cutoffs_by_date"] == {
        "2026-01-01": "2025-12-31T11:00:00Z",
        "2026-01-02": "2026-01-01T11:00:00Z",
    }
    assert data["mae_unit"] == "MW"
    assert data["mape_unit"] == "%"
    assert "unique_hourly_forecast_count" in data
    assert "forecast_covered_interval_count" in data


# ---------------------------------------------------------------------------
# Phase 5 Audit: Date Boundaries, Cutoffs & Coverage Distinction Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_one_day_request_metadata(test_db):
    """One-day analytics request: verify inclusive metadata and per-date cutoff map."""
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, ts, 10000.0)
    await _add_forecast(test_db, ts, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 10500.0)

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")

    assert result.date_range_start == "2026-01-01"
    assert result.date_range_end == "2026-01-01"
    assert result.date_boundary_type == "inclusive"
    assert result.cutoff_time_local == "11:00"
    assert result.cutoff_timezone == "Europe/London"
    assert result.cutoff_applied_per_delivery_date is True
    assert result.decision_cutoff_utc == "2025-12-31T11:00:00Z"
    assert result.decision_cutoffs_by_date == {"2026-01-01": "2025-12-31T11:00:00Z"}
    assert result.expected_interval_count == 48
    assert result.unique_actual_records_count == 1
    assert result.unique_hourly_forecast_count == 1
    assert result.forecast_covered_interval_count == 2
    assert result.matched_interval_count == 1


@pytest.mark.asyncio
async def test_analytics_two_day_inclusive_distinct_cutoffs(test_db):
    """Two-day inclusive request: Jan 1 and Jan 2 use separate D-1 decision cutoffs."""
    # Jan 1 cutoff is 2025-12-31 11:00 UTC
    # Jan 2 cutoff is 2026-01-01 11:00 UTC

    # Forecast published at 2025-12-31 11:30 UTC:
    # - Ineligible for Jan 1 (published after Jan 1 cutoff 11:00)
    # - ELIGIBLE for Jan 2 (published before Jan 2 cutoff 2026-01-01 11:00)
    ts_jan1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    ts_jan2 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC_TZ)

    await _add_actual(test_db, ts_jan1, 10000.0)
    await _add_actual(test_db, ts_jan2, 12000.0)

    # Forecast for Jan 1 published after Jan 1 cutoff
    await _add_forecast(test_db, ts_jan1, datetime(2025, 12, 31, 11, 30, 0, tzinfo=UTC_TZ), 11000.0)
    # Forecast for Jan 2 published at same timestamp (which is BEFORE Jan 2 cutoff)
    await _add_forecast(test_db, ts_jan2, datetime(2025, 12, 31, 11, 30, 0, tzinfo=UTC_TZ), 12500.0)

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 2), "11:00")

    assert result.date_range_start == "2026-01-01"
    assert result.date_range_end == "2026-01-02"
    assert result.expected_interval_count == 96
    assert result.decision_cutoffs_by_date == {
        "2026-01-01": "2025-12-31T11:00:00Z",
        "2026-01-02": "2026-01-01T11:00:00Z",
    }
    # Jan 1 forecast was rejected, so only Jan 2 is matched!
    assert result.matched_interval_count == 1
    assert result.unique_hourly_forecast_count == 1
    assert result.mae_mw == pytest.approx(500.0, rel=1e-4)


@pytest.mark.asyncio
async def test_forecast_published_exactly_at_cutoff_is_eligible(test_db):
    """Forecast published exactly at D-1 11:00:00 UTC must be eligible (<= condition)."""
    ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, ts, 10000.0)
    await _add_forecast(test_db, ts, datetime(2025, 12, 31, 11, 0, 0, tzinfo=UTC_TZ), 10200.0)

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")

    assert result.matched_interval_count == 1
    assert result.mae_mw == pytest.approx(200.0, rel=1e-4)


@pytest.mark.asyncio
async def test_forecast_published_after_cutoff_is_ineligible(test_db):
    """Forecast published at D-1 11:00:01 UTC must NOT be eligible."""
    ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, ts, 10000.0)
    await _add_forecast(test_db, ts, datetime(2025, 12, 31, 11, 0, 1, tzinfo=UTC_TZ), 10200.0)

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")

    assert result.matched_interval_count == 0
    assert result.mae_mw is None


@pytest.mark.asyncio
async def test_missing_forecast_on_one_settlement_interval(test_db):
    """Interval with actual but no eligible forecast must not be matched or zeroed."""
    ts_matched = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    ts_unmatched = datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC_TZ)

    await _add_actual(test_db, ts_matched, 10000.0)
    await _add_actual(test_db, ts_unmatched, 12000.0)
    await _add_forecast(test_db, ts_matched, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 10300.0)
    # No forecast for 11:00

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")

    assert result.actual_interval_count == 2
    assert result.forecast_covered_interval_count == 2  # 10:00 forecast covers 10:00 and 10:30
    assert result.matched_interval_count == 1          # only 10:00 has both actual and forecast
    assert result.mae_mw == pytest.approx(300.0, rel=1e-4)


@pytest.mark.asyncio
async def test_missing_actual_on_one_settlement_interval(test_db):
    """Hourly forecast covers two half-hours; if 10:30 actual is missing, only 10:00 is matched."""
    ts_10_00 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC_TZ)
    ts_10_30 = datetime(2026, 1, 1, 10, 30, 0, tzinfo=UTC_TZ)

    # Actual only for 10:00
    await _add_actual(test_db, ts_10_00, 10000.0)
    # 1-hour forecast for 10:00 covers both 10:00 and 10:30
    await _add_forecast(test_db, ts_10_00, datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ), 10400.0)

    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")

    assert result.actual_interval_count == 1
    assert result.unique_actual_records_count == 1
    assert result.unique_hourly_forecast_count == 1
    assert result.forecast_covered_interval_count == 2
    assert result.matched_interval_count == 1
    assert result.mae_mw == pytest.approx(400.0, rel=1e-4)


@pytest.mark.asyncio
async def test_multiple_publication_vintages_selection(test_db):
    """For multiple vintages, latest publication at or before cutoff must be selected."""
    deliv_ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC_TZ)
    await _add_actual(test_db, deliv_ts, 10000.0)

    # Add 4 vintages for the same delivery interval:
    # 1. 06:00 (10000 MW)
    await _add_forecast(test_db, deliv_ts, datetime(2025, 12, 31, 6, 0, 0, tzinfo=UTC_TZ), 10000.0)
    # 2. 09:00 (11000 MW)
    await _add_forecast(test_db, deliv_ts, datetime(2025, 12, 31, 9, 0, 0, tzinfo=UTC_TZ), 11000.0)
    # 3. 10:59 (12500 MW) - latest before 11:00 cutoff
    await _add_forecast(test_db, deliv_ts, datetime(2025, 12, 31, 10, 59, 0, tzinfo=UTC_TZ), 12500.0)
    # 4. 11:30 (15000 MW) - post-cutoff
    await _add_forecast(test_db, deliv_ts, datetime(2025, 12, 31, 11, 30, 0, tzinfo=UTC_TZ), 15000.0)

    svc = AccuracyService(db=test_db)
    result_11 = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")
    # Under 11:00 cutoff, 10:59 vintage (12500 MW) must be selected: err = 12500 - 10000 = 2500
    assert result_11.mae_mw == pytest.approx(2500.0, rel=1e-4)

    # Under 08:00 cutoff, 06:00 vintage (10000 MW) must be selected: err = 10000 - 10000 = 0
    result_08 = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "08:00")
    assert result_08.mae_mw == pytest.approx(0.0, rel=1e-4)


@pytest.mark.asyncio
async def test_duplicate_database_records_prevention_and_aggregation_safety(test_db):
    """Schema unique constraints and selection logic prevent duplicate rows from multiplying metrics."""
    from sqlalchemy.exc import IntegrityError

    deliv_ts = datetime(2026, 1, 1, 15, 0, 0, tzinfo=UTC_TZ)
    pub_ts = datetime(2025, 12, 31, 8, 0, 0, tzinfo=UTC_TZ)

    await _add_actual(test_db, deliv_ts, 10000.0)
    await _add_forecast(test_db, deliv_ts, pub_ts, 10500.0)

    # Attempting to insert duplicate actual record for same (delivery_timestamp, source) must fail
    dup_actual = ActualGeneration(
        delivery_timestamp=deliv_ts,
        delivery_date=date(2026, 1, 1),
        settlement_period=31,
        generation_mw=9999.0,
        fuel_type="WIND",
        source="ELEXON_FUELHH",
    )
    test_db.add(dup_actual)
    with pytest.raises(IntegrityError):
        await test_db.commit()
    await test_db.rollback()

    # Query result must have exactly 1 matched interval
    svc = AccuracyService(db=test_db)
    result = await svc.compute_accuracy(date(2026, 1, 1), date(2026, 1, 1), "11:00")
    assert result.matched_interval_count == 1
    assert result.actual_interval_count == 1
    assert result.mae_mw == pytest.approx(500.0, rel=1e-4)
