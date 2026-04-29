"""Shared utilities."""

import json
from datetime import datetime, timezone
from typing import Any


def safe_json_loads(raw: str | None, default: Any = None) -> Any:
    """Parse a JSON string, returning *default* on None or malformed input."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def utcnow_naive() -> datetime:
    """Return current UTC time as a timezone-naive datetime.

    Every timestamp column in this codebase is declared as a plain
    SQLAlchemy ``DateTime`` (which becomes ``TIMESTAMP WITHOUT TIME ZONE``
    on Postgres). Postgres ``asyncpg`` refuses to silently strip ``tzinfo``
    when writing a tz-aware datetime to a tz-naive column — it raises
    ``DataError: can't subtract offset-naive and offset-aware datetimes``.

    Production run #25122197274 hit this exact error at the Designer
    stage: ``paper.lock_timestamp = datetime.now(timezone.utc)`` was
    being written to a ``TIMESTAMP WITHOUT TIME ZONE`` column.

    Use this helper for every assignment to an ORM ``DateTime`` field.
    For *comparisons* (e.g. ``cutoff = datetime.now(timezone.utc) -
    timedelta(...)``), keep using tz-aware datetimes — they're correct
    semantically and never written to disk.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
