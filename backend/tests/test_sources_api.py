"""Tests for the sources API endpoints (GET /sources, /sources/{id}, /sources/{id}/snapshots)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_card import SourceCard


@pytest_asyncio.fixture
async def source_data(db_session: AsyncSession):
    """Create source cards for testing."""
    src1 = SourceCard(
        id="federal_register",
        name="Federal Register",
        url="https://www.federalregister.gov",
        tier="T1",
        source_type="government",
        update_frequency="daily",
        access_method="api",
        requires_key=False,
        canonical_unit="rule",
        claim_permissions='["regulatory_text", "enforcement_actions"]',
        claim_prohibitions='["draft_rules"]',
        fragility_score=0.1,
        active=True,
    )
    src2 = SourceCard(
        id="courtlistener",
        name="CourtListener",
        url="https://www.courtlistener.com",
        tier="T2",
        source_type="legal",
        update_frequency="daily",
        access_method="api",
        requires_key=True,
        canonical_unit="opinion",
        claim_permissions='["judicial_opinions"]',
        claim_prohibitions='[]',
        fragility_score=0.3,
        active=True,
    )
    src_inactive = SourceCard(
        id="deprecated_src",
        name="Deprecated Source",
        url="https://example.com",
        tier="T3",
        source_type="other",
        update_frequency="never",
        access_method="scrape",
        requires_key=False,
        canonical_unit="page",
        claim_permissions='[]',
        claim_prohibitions='[]',
        fragility_score=0.9,
        active=False,
    )
    db_session.add_all([src1, src2, src_inactive])
    await db_session.commit()
    return [src1, src2, src_inactive]


# ── GET /sources ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_sources_empty(client):
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_sources(client, source_data):
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2  # active_only default
    ids = [s["id"] for s in data["sources"]]
    assert "federal_register" in ids
    assert "deprecated_src" not in ids


@pytest.mark.asyncio
async def test_list_sources_include_inactive(client, source_data):
    resp = await client.get("/api/v1/sources?active_only=false")
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


@pytest.mark.asyncio
async def test_list_sources_filter_by_tier(client, source_data):
    resp = await client.get("/api/v1/sources?tier=T1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["sources"][0]["id"] == "federal_register"


# ── GET /sources/{source_id} ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_source_detail(client, source_data):
    resp = await client.get("/api/v1/sources/federal_register")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "federal_register"
    assert data["name"] == "Federal Register"
    assert data["requires_key"] is False


@pytest.mark.asyncio
async def test_get_source_not_found(client):
    resp = await client.get("/api/v1/sources/nonexistent")
    assert resp.status_code == 404


# ── GET /sources/{source_id}/snapshots ────────────────────────────────────────

@pytest.mark.asyncio
async def test_snapshots_empty(client, source_data):
    """Source with no snapshots returns empty list."""
    resp = await client.get("/api/v1/sources/federal_register/snapshots")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_id"] == "federal_register"
    assert data["snapshots"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_snapshots_source_not_found(client):
    resp = await client.get("/api/v1/sources/nonexistent/snapshots")
    assert resp.status_code == 404
