"""Tests for the health endpoint and core middleware."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health check returns ok status."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_request_id(client):
    """Health response includes X-Request-ID header."""
    resp = await client.get("/health")
    # RequestIDMiddleware should set this
    assert "x-request-id" in resp.headers


@pytest.mark.asyncio
async def test_security_headers(client):
    """Responses include security headers."""
    resp = await client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "strict-origin" in resp.headers.get("referrer-policy", "")


@pytest.mark.asyncio
async def test_cors_headers(client):
    """CORS preflight returns correct headers."""
    resp = await client.options(
        "/api/v1/papers",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Should not be 405 — CORS middleware handles OPTIONS
    assert resp.status_code in (200, 204)


@pytest.mark.asyncio
async def test_custom_request_id_passthrough(client):
    """Custom X-Request-ID in request is echoed back."""
    resp = await client.get("/health", headers={"X-Request-ID": "custom-123"})
    assert resp.headers.get("x-request-id") == "custom-123"
