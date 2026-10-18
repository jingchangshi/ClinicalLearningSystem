"""Server time is UTC. The database stores naive UTC; the API speaks ISO-8601 with ``Z``."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(value: datetime) -> datetime:
    """Convert an *offset-aware* datetime to naive UTC. Naive input is a caller error."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone offset required (send e.g. 2026-11-02T08:00:00+08:00 or ...Z)")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + "Z"
