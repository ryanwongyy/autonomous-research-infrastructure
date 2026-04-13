"""Shared utilities."""

import json
from typing import Any


def safe_json_loads(raw: str | None, default: Any = None) -> Any:
    """Parse a JSON string, returning *default* on None or malformed input."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default
