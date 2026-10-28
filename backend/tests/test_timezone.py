from datetime import date, datetime
from zoneinfo import ZoneInfo
import pytest
from backend.app.core.timezone import (
    UK_TZ,
    UTC_TZ,
    ensure_utc,
    parse_iso_to_utc,
    format_utc_iso,
    to_uk_local,
    get_delivery_date_for_interval,
    calculate_decision_cutoff,
    calculate_settlement_period,
    get_delivery_day_bounds_utc,
)


def test_ensure_utc_naive_and_aware():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    aware = ensure_utc(naive)
    assert aware.tzinfo == UTC_TZ
    assert aware.hour == 12

    uk_dt = datetime(2026, 7, 1, 13, 0, 0, tzinfo=UK_TZ)  # BST (UTC+1)
    utc_dt = ensure_utc(uk_dt)
    assert utc_dt.tzinfo == UTC_TZ
    assert utc_dt.hour == 12  # 13:00 BST == 12:00 UTC


def test_parse_iso_to_utc():
    iso_str = "2026-01-01T23:30:00Z"
    dt = parse_iso_to_utc(iso_str)
    assert dt.year == 2026
    assert dt.month == 1
    assert dt.day == 1
    assert dt.hour == 23
    assert dt.minute == 30
    assert dt.tzinfo == UTC_TZ

    iso_offset = "2026-01-01T23:30:00+00:00"
    dt2 = parse_iso_to_utc(iso_offset)
    assert dt2 == dt


def test_format_utc_iso():
    dt = datetime(2026, 1, 15, 8, 30, 0, tzinfo=UTC_TZ)
    assert format_utc_iso(dt) == "2026-01-15T08:30:00Z"


def test_get_delivery_date_for_interval():
    # 2026-01-01 00:00 UTC is in delivery date 2026-01-01
    dt1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ)
    assert get_delivery_date_for_interval(dt1) == date(2026, 1, 1)

    # 2026-01-01 23:30 UTC is still 2026-01-01
    dt2 = datetime(2026, 1, 1, 23, 30, 0, tzinfo=UTC_TZ)
    assert get_delivery_date_for_interval(dt2) == date(2026, 1, 1)


def test_calculate_decision_cutoff_default_and_custom():
    delivery_date = date(2026, 1, 1)
    # Default 11:00 on D-1 (2025-12-31)
    cutoff = calculate_decision_cutoff(delivery_date, "11:00")
    assert cutoff.year == 2025
    assert cutoff.month == 12
    assert cutoff.day == 31
    assert cutoff.hour == 11
    assert cutoff.minute == 0
    assert cutoff.tzinfo == UTC_TZ

    # Configurable 09:30 cutoff
    cutoff_early = calculate_decision_cutoff(delivery_date, "09:30")
    assert cutoff_early.day == 31
    assert cutoff_early.hour == 9
    assert cutoff_early.minute == 30


def test_calculate_settlement_period():
    # SP 1: 00:00 to 00:30
    dt_sp1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ)
    assert calculate_settlement_period(dt_sp1) == 1

    # SP 2: 00:30 to 01:00
    dt_sp2 = datetime(2026, 1, 1, 0, 30, 0, tzinfo=UTC_TZ)
    assert calculate_settlement_period(dt_sp2) == 2

    # SP 25: 12:00 to 12:30 (12 * 2 + 1)
    dt_sp25 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
    assert calculate_settlement_period(dt_sp25) == 25

    # SP 48: 23:30 to 24:00
    dt_sp48 = datetime(2026, 1, 1, 23, 30, 0, tzinfo=UTC_TZ)
    assert calculate_settlement_period(dt_sp48) == 48


def test_delivery_day_bounds_utc():
    d = date(2026, 1, 1)
    start_utc, end_utc = get_delivery_day_bounds_utc(d)
    assert start_utc == datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ)
    assert end_utc == datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC_TZ)


def test_dst_spring_forward_23_hours():
    """UK clocks spring forward on the last Sunday of March (2026-03-29) creating a 23-hour day."""
    spring_dst_date = date(2026, 3, 29)
    start_utc, end_utc = get_delivery_day_bounds_utc(spring_dst_date)
    duration_hours = (end_utc - start_utc).total_seconds() / 3600.0
    assert duration_hours == 23.0, f"Expected 23-hour day on UK spring clock change, got {duration_hours}"


def test_dst_autumn_fall_back_25_hours():
    """UK clocks fall back on the last Sunday of October (2026-10-25) creating a 25-hour day."""
    autumn_dst_date = date(2026, 10, 25)
    start_utc, end_utc = get_delivery_day_bounds_utc(autumn_dst_date)
    duration_hours = (end_utc - start_utc).total_seconds() / 3600.0
    assert duration_hours == 25.0, f"Expected 25-hour day on UK autumn clock change, got {duration_hours}"


def test_dst_cutoff_conversion_winter_vs_summer():
    """11:00 UK local time is 11:00 UTC in GMT (winter) and 10:00 UTC in BST (summer)."""
    # Winter delivery date (2026-01-02 -> D-1 is 2026-01-01 GMT)
    winter_cutoff = calculate_decision_cutoff(date(2026, 1, 2), "11:00")
    assert winter_cutoff == datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC_TZ)

    # Summer delivery date (2026-07-02 -> D-1 is 2026-07-01 BST = UTC+1)
    summer_cutoff = calculate_decision_cutoff(date(2026, 7, 2), "11:00")
    assert summer_cutoff == datetime(2026, 7, 1, 10, 0, 0, tzinfo=UTC_TZ)

