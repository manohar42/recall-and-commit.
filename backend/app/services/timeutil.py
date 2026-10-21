from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/Phoenix"


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return as_utc(value)
    try:
        return as_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


def format_local(value, tz_name: str = DEFAULT_TZ) -> str:
    dt = parse_iso(value)
    if dt is None:
        return "an unknown time"
    local = dt.astimezone(ZoneInfo(tz_name))
    return local.strftime("%a %b %d, %Y %I:%M %p").replace(" 0", " ")


def format_range(start, end, tz_name: str = DEFAULT_TZ) -> str:
    """'Sat Oct 24, 2026 4:45 PM to 6:15 PM' when both ends fall on the same local day."""
    a, b = parse_iso(start), parse_iso(end)
    if a is None or b is None:
        return format_local(start or end, tz_name)
    za, zb = a.astimezone(ZoneInfo(tz_name)), b.astimezone(ZoneInfo(tz_name))
    if za.date() == zb.date():
        return f"{format_local(a, tz_name)} to {zb.strftime('%I:%M %p').lstrip('0')}"
    return f"{format_local(a, tz_name)} to {format_local(b, tz_name)}"
