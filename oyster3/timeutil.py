"""Time helpers. TTN timestamps are UTC with up to nanosecond precision, e.g.
``2025-01-05T13:56:56.256908367Z``. ``datetime.fromisoformat`` on Python 3.10 accepts
neither the ``Z`` suffix nor more than six fractional digits."""

import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Europe/Amsterdam"

_TIMESTAMP = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$"
)


def parse_ttn_timestamp(text: str) -> datetime:
    """Parse a TTN/RFC 3339 timestamp into an aware UTC datetime (sub-microseconds dropped)."""
    match = _TIMESTAMP.match(text.strip())
    if not match:
        raise ValueError(f"not a timestamp: {text!r}")
    date, clock, fraction, zone = match.groups()
    if clock.count(":") == 1:
        clock += ":00"
    micro = (fraction or "")[:6].ljust(6, "0")
    if zone in (None, "Z"):
        zone = "+00:00"
    elif ":" not in zone:
        zone = zone[:3] + ":" + zone[3:]
    parsed = datetime.fromisoformat(f"{date}T{clock}.{micro}{zone}")
    return parsed.astimezone(timezone.utc)


def to_ttn_timestamp(moment: datetime) -> str:
    """Format an aware datetime as an RFC 3339 UTC timestamp for TTN query parameters."""
    if moment.tzinfo is None:
        raise ValueError("naive datetime; use an aware datetime")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def app_timezone(environ=os.environ) -> ZoneInfo:
    return ZoneInfo(environ.get("APP_TIMEZONE") or DEFAULT_TIMEZONE)


def local_input_to_utc(text: str, zone: ZoneInfo) -> datetime:
    """Convert an HTML datetime-local value (YYYY-mm-ddTHH:MM, local time) to aware UTC."""
    naive = datetime.strptime(text, "%Y-%m-%dT%H:%M")
    return naive.replace(tzinfo=zone).astimezone(timezone.utc)


def format_local(moment: datetime, zone: ZoneInfo) -> str:
    return moment.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S %Z")
