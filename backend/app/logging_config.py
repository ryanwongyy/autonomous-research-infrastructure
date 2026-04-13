"""Structured logging configuration.

In production (DATABASE_URL starts with 'postgresql'), logs are JSON-formatted
for aggregation tools. In development, logs use human-readable format.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.config import settings

_is_production = not settings.database_url.startswith("sqlite")


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            entry["request_id"] = record.request_id
        return json.dumps(entry, default=str)


def configure_logging() -> None:
    """Set up root logger with appropriate formatter."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if _is_production:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s")
        )
    root.addHandler(handler)

    # Suppress noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
