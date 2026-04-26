"""Tests for the batch orchestration API endpoints.

These endpoints require admin key auth. We test the auth gate
and the seed-families endpoint (which doesn't call external LLM APIs).

Note: batch.py uses `async_session` directly (not dependency injection),
so we must monkeypatch `app.api.batch.async_session` for tests to use
the test database.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_db

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_client(db_engine, monkeypatch):
    """Client with admin key for batch endpoints.

    Patches both the DI get_db AND the direct async_session import in batch.py
    so that all DB access uses the test engine.
    """
    monkeypatch.setattr("app.config.settings.ape_api_key", "test-api-key")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "test-admin-key")

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Patch the direct async_session used in batch.py
    monkeypatch.setattr("app.api.batch.async_session", session_factory)

    from app.main import app

    async def _test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ── Auth gating ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_endpoints_require_admin_key(client, monkeypatch):
    """Batch endpoints reject requests without admin key."""
    monkeypatch.setattr("app.config.settings.ape_api_key", "regular-key")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "admin-key")

    # Regular key should be rejected (403)
    endpoints = [
        "/api/v1/batch/seed-families",
        "/api/v1/batch/review-pending",
        "/api/v1/batch/promote",
    ]
    for ep in endpoints:
        resp = await client.post(ep, headers={"X-API-Key": "regular-key"})
        assert resp.status_code == 403, f"{ep} should require admin key"


# ── POST /batch/seed-families ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_families_creates_families(admin_client):
    """Seed endpoint creates families in an empty database."""
    resp = await admin_client.post("/api/v1/batch/seed-families")
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "seed-families"
    # Should have created some families
    created = [r for r in data["results"] if r["status"] == "created"]
    assert len(created) > 0
    assert "Seeded" in data["summary"]


@pytest.mark.asyncio
async def test_seed_families_idempotent(admin_client):
    """Running seed-families twice doesn't duplicate families."""
    resp1 = await admin_client.post("/api/v1/batch/seed-families")
    assert resp1.status_code == 200
    created_count = len([r for r in resp1.json()["results"] if r["status"] == "created"])
    assert created_count > 0  # First call must create

    resp2 = await admin_client.post("/api/v1/batch/seed-families")
    assert resp2.status_code == 200
    data2 = resp2.json()
    # Second call should find everything already exists
    already_exists = [r for r in data2["results"] if r["status"] == "already_exists"]
    assert len(already_exists) == created_count


# ── POST /batch/review-pending ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_pending_empty(admin_client):
    """Review-pending with no awaiting papers returns empty results."""
    resp = await admin_client.post("/api/v1/batch/review-pending")
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "review-pending"
    assert data["results"] == []


# ── POST /batch/promote ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_promote_empty(admin_client):
    """Promote with no eligible papers returns empty results."""
    resp = await admin_client.post("/api/v1/batch/promote")
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "promote"
    assert data["results"] == []
    assert "Promoted 0" in data["summary"]


# ── POST /batch/generate ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_no_families(admin_client):
    """Generate with no families returns 'no active families' summary."""
    resp = await admin_client.post(
        "/api/v1/batch/generate",
        json={"count": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "generate"
    assert "No active families" in data["summary"]


@pytest.mark.asyncio
async def test_generate_request_validation(admin_client):
    """Generate validates count bounds."""
    # count=0 should fail validation
    resp = await admin_client.post(
        "/api/v1/batch/generate",
        json={"count": 0},
    )
    assert resp.status_code == 422

    # count=11 should fail validation (max 10)
    resp2 = await admin_client.post(
        "/api/v1/batch/generate",
        json={"count": 11},
    )
    assert resp2.status_code == 422
