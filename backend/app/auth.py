"""API key authentication.

Two tiers:
  - api_key_required: gates all mutation endpoints (POST/PUT/PATCH/DELETE).
  - admin_key_required: gates expensive operations (RSI cycles, tournament runs,
    bulk imports) that burn LLM credits or mutate core system state.

Keys are checked from the ``Authorization: Bearer <key>`` header or the
``X-API-Key`` header.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from app.config import settings

logger = logging.getLogger(__name__)

_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def _extract_key(request: Request, header_value: str | None) -> str | None:
    """Extract the API key from X-API-Key header or Authorization: Bearer."""
    if header_value:
        return header_value
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def api_key_required(
    request: Request,
    header_value: str | None = Depends(_header_scheme),
) -> None:
    """Dependency that enforces a valid API key for mutation endpoints."""
    if not settings.ape_api_key:
        # Auth not configured — allow (dev mode)
        return

    key = _extract_key(request, header_value)
    if not key or not hmac.compare_digest(key, settings.ape_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def admin_key_required(
    request: Request,
    header_value: str | None = Depends(_header_scheme),
) -> None:
    """Dependency that enforces the admin API key for dangerous operations."""
    if not settings.ape_admin_key:
        # Fall back to regular API key check
        await api_key_required(request, header_value)
        return

    key = _extract_key(request, header_value)
    if not key or not hmac.compare_digest(key, settings.ape_admin_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin API key required for this operation",
        )
