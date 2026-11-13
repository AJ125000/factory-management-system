from __future__ import annotations

import uuid
from datetime import UTC, date, datetime


def new_id() -> str:
    """Random UUID primary keys, so records made on different devices never clash when synced."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (SQLite has no timezone type)."""
    return datetime.now(UTC).replace(tzinfo=None)


def today() -> date:
    """The local calendar date (wages are dated by the factory's day, not UTC)."""
    return date.today()
