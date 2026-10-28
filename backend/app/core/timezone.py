"""Timezone and settlement period utilities for UK Electricity Market data.

Strict Domain Rules:
1. All database timestamps and internal comparisons are strictly timezone-aware UTC.
2. All business-facing dates and decision cutoffs are defined in Europe/London.
3. For delivery date D, the Day-Ahead decision cutoff occurs on D-1 at the configured
   cutoff time (e.g. 11:00 Europe/London), converted to UTC for database comparison.
4. No naive datetime strings are permitted for filtering or comparison.
"""

from datetime import date, datetime, time, timedelta
from typing import Tuple, Optional
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")
UTC_TZ = ZoneInfo("UTC")


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware and converted to UTC."""
    if dt.tzinfo is None:
        # If naive, assume UTC as standard internal default
        return dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(UTC_TZ)


def parse_iso_to_utc(iso_str: str) -> datetime:
    """Parse an ISO 8601 string to a UTC-aware datetime.
    
    Handles strings ending with 'Z' or standard offset '+00:00'.
    """
    clean_str = iso_str.strip()
    if clean_str.endswith("Z"):
        clean_str = clean_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(clean_str)
    return ensure_utc(dt)


def format_utc_iso(dt: datetime) -> str:
    """Format a UTC datetime to standard ISO 8601 string with Z suffix."""
    utc_dt = ensure_utc(dt)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_uk_local(dt: datetime) -> datetime:
    """Convert any timezone-aware datetime to Europe/London."""
    aware_dt = ensure_utc(dt)
    return aware_dt.astimezone(UK_TZ)


def get_delivery_date_for_interval(interval_start_utc: datetime) -> date:
    """Derive the GB business delivery date (Europe/London) for a 30-min settlement interval."""
    local_dt = to_uk_local(interval_start_utc)
    return local_dt.date()


def calculate_decision_cutoff(
    delivery_date: date,
    cutoff_time_str: str = "11:00"
) -> datetime:
    """Calculate the exact Day-Ahead decision cutoff timestamp in UTC.
    
    For a given delivery date D:
    - Decision date is D - 1 day.
    - Decision cutoff time is cutoff_time_str (e.g. "11:00") in Europe/London.
    - Result is converted to UTC for exact database timestamp filtering.
    
    Example:
        delivery_date = 2026-01-01
        cutoff_time_str = "11:00"
        -> 2025-12-31 11:00:00 Europe/London == 2025-12-31 11:00:00 UTC (GMT)
    """
    decision_date = delivery_date - timedelta(days=1)
    
    # Parse HH:MM
    parts = cutoff_time_str.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    
    cutoff_local = datetime.combine(
        decision_date,
        time(hour=hour, minute=minute),
        tzinfo=UK_TZ
    )
    return cutoff_local.astimezone(UTC_TZ)


def get_delivery_day_bounds_utc(delivery_date: date) -> Tuple[datetime, datetime]:
    """Get the start and end timestamps in UTC for a delivery day in Europe/London.
    
    Returns:
        (start_utc, end_utc):
        start_utc is 00:00:00 UK local time converted to UTC.
        end_utc is 00:00:00 UK local time of next day converted to UTC (exclusive bound).
    """
    start_local = datetime.combine(delivery_date, time(0, 0, 0), tzinfo=UK_TZ)
    end_local = datetime.combine(delivery_date + timedelta(days=1), time(0, 0, 0), tzinfo=UK_TZ)
    return start_local.astimezone(UTC_TZ), end_local.astimezone(UTC_TZ)


def calculate_settlement_period(interval_start_utc: datetime) -> int:
    """Calculate the 30-minute settlement period number (1 to 48) in UK local time.
    
    Settlement Period 1: 00:00 to 00:30
    Settlement Period 2: 00:30 to 01:00
    ...
    Settlement Period 48: 23:30 to 24:00
    """
    local_dt = to_uk_local(interval_start_utc)
    minute_of_day = local_dt.hour * 60 + local_dt.minute
    sp = (minute_of_day // 30) + 1
    return sp
