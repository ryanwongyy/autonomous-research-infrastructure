"""Tests for the API key authentication middleware and dependencies."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_db


@pytest_asyncio.fixture
async def auth_client(db_engine, monkeypatch):
    """Client pointing at an app with auth enabled."""
    monkeypatch.setattr("app.config.settings.ape_api_key", "test-key-123")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "admin-key-456")

    from app.main import app

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── GET requests pass without auth ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_requests_need_no_auth(auth_client):
    resp = await auth_client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_papers_no_auth(auth_client):
    resp = await auth_client.get("/api/v1/papers")
    assert resp.status_code == 200


# ── Mutations require API key ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_without_key_returns_401(auth_client):
    resp = await auth_client.post(
        "/api/v1/papers",
        json={"title": "Test Paper"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_with_wrong_key_returns_401(auth_client):
    resp = await auth_client.post(
        "/api/v1/papers",
        json={"title": "Test Paper"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_with_valid_key_passes_auth(auth_client):
    resp = await auth_client.post(
        "/api/v1/papers",
        json={"title": "Test Paper", "source": "ape"},
        headers={"X-API-Key": "test-key-123"},
    )
    # Should not be 401 — may be 422 (validation) or 200, but NOT 401
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_bearer_token_works(auth_client):
    resp = await auth_client.post(
        "/api/v1/papers",
        json={"title": "Test Paper", "source": "ape"},
        headers={"Authorization": "Bearer test-key-123"},
    )
    assert resp.status_code != 401


# ── Admin endpoints require admin key ──────────────────────────────────────

@pytest.mark.asyncio
async def test_tournament_needs_admin_key(auth_client):
    resp = await auth_client.post(
        "/api/v1/tournament/run?family_id=all",
        headers={"X-API-Key": "test-key-123"},  # Regular key, not admin
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tournament_with_admin_key(auth_client):
    resp = await auth_client.post(
        "/api/v1/tournament/run?family_id=test",
        headers={"X-API-Key": "admin-key-456"},
    )
    # Should pass auth (may fail on business logic, but not 401/403)
    assert resp.status_code not in (401, 403)


# ── Dev mode (no key configured) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_dev_mode_allows_all(client):
    """When ape_api_key is empty, all requests pass."""
    resp = await client.post(
        "/api/v1/papers",
        json={"title": "Dev Paper", "source": "ape"},
    )
    assert resp.status_code != 401
