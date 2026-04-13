"""Tests for the RSI API endpoints.

RSI routes are mounted with admin_key_required dependency,
so all requests need the admin key.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_db


@pytest_asyncio.fixture
async def admin_client(db_engine, monkeypatch):
    """Client with admin key for RSI endpoints."""
    monkeypatch.setattr("app.config.settings.ape_api_key", "test-api-key")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "test-admin-key")

    from app.main import app

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

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


@pytest_asyncio.fixture
async def non_admin_client(db_engine, monkeypatch):
    """Client with regular (non-admin) API key."""
    monkeypatch.setattr("app.config.settings.ape_api_key", "test-api-key")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "test-admin-key")

    from app.main import app

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-api-key"},
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ── Admin access required ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rsi_dashboard_needs_admin_key(non_admin_client):
    resp = await non_admin_client.get("/api/v1/rsi/dashboard")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rsi_dashboard_with_admin_key(admin_client):
    resp = await admin_client.get("/api/v1/rsi/dashboard")
    assert resp.status_code == 200


# ── Dashboard & experiments ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rsi_experiments_empty(admin_client):
    resp = await admin_client.get("/api/v1/rsi/experiments")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rsi_experiment_not_found(admin_client):
    resp = await admin_client.get("/api/v1/rsi/experiments/99999")
    assert resp.status_code == 404


# ── Tier status GETs ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tier1a_status(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier1a/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier1b_accuracy(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier1b/accuracy")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier1c_status(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier1c/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier2a_health(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier2a/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier2b_metrics(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier2b/metrics")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier2c_overview(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier2c/overview")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier3a_effectiveness(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier3a/effectiveness")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier3b_boundary_failures(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier3b/boundary-failures")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier3c_clusters(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier3c/clusters")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier4a_clusters(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier4a/clusters")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier4b_cohort_deltas(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier4b/cohort-deltas")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tier4c_runs_empty(admin_client):
    resp = await admin_client.get("/api/v1/rsi/tier4c/runs")
    assert resp.status_code == 200
