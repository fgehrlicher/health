"""The person's local time: days start at local midnight in HEALTH_TIMEZONE."""

import os
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from health_api.ingredients import InputError

# Accept slightly future times from clock skew, not planned meals or cooks.
FUTURE_TOLERANCE = timedelta(minutes=10)


def timezone() -> ZoneInfo:
    return ZoneInfo(os.environ.get("HEALTH_TIMEZONE", "Europe/Berlin"))


def local_time(value: datetime | None, field: str = "eaten_at") -> datetime:
    """The time with the local zone when it has no offset; default now; never future."""
    zone = timezone()
    if value is None:
        return datetime.now(zone)
    value = value.replace(tzinfo=zone) if value.tzinfo is None else value
    if value > datetime.now(UTC) + FUTURE_TOLERANCE:
        raise InputError([{"field": field, "message": "lies in the future"}])
    return value


def day_bounds(day: date) -> tuple[datetime, datetime]:
    zone = timezone()
    return datetime.combine(day, time(), zone), datetime.combine(day + timedelta(1), time(), zone)
