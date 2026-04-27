"""Tests for reliability and outcomes API endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily


@pytest_asyncio.fixture
async def reliability_data(db_session: AsyncSession):
    """Create data for reliability and outcomes tests."""
    family = PaperFamily(
        id="F1",
        name="Test",
        short_name="T",
        description="For reliability tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    paper = Paper(
        id="rel_paper",
        title="Reliability Test Paper",
        source="ape",
        family_id="F1",
        status="published",
        review_status="peer_reviewed",
    )
    db_session.add(paper)
    await db_session.commit()
    return paper


# ── GET /reliability/overview ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reliability_overview_empty(client):
    resp = await client.get("/api/v1/reliability/overview")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reliability_overview_with_data(client, reliability_data):
    resp = await client.get("/api/v1/reliability/overview")
    assert resp.status_code == 200


# ── GET /reliability/family/{family_id} ───────────────────────────────────────


@pytest.mark.asyncio
async def test_reliability_family(client, reliability_data):
    resp = await client.get("/api/v1/reliability/family/F1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["family_id"] == "F1"


# ── GET /reliability/paper/{paper_id} ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_reliability_paper(client, reliability_data):
    resp = await client.get("/api/v1/reliability/paper/rel_paper")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "rel_paper"


# ── GET /papers/{id}/outcomes ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outcomes_empty(client, reliability_data):
    """Paper with no outcomes returns empty list."""
    resp = await client.get("/api/v1/papers/rel_paper/outcomes")
    assert resp.status_code == 200
    assert resp.json() == []


# ── POST /papers/{id}/outcomes ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_outcome(client, reliability_data):
    resp = await client.post(
        "/api/v1/papers/rel_paper/outcomes",
        json={
            "venue_name": "Nature Machine Intelligence",
            "submitted_date": "2025-01-15",
            "decision": "revise_and_resubmit",
            "revision_rounds": 1,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "rel_paper"
    assert data["venue_name"] == "Nature Machine Intelligence"


@pytest.mark.asyncio
async def test_create_outcome_then_list(client, reliability_data):
    """Creating an outcome makes it visible in the list endpoint."""
    await client.post(
        "/api/v1/papers/rel_paper/outcomes",
        json={"venue_name": "AJPS", "submitted_date": "2025-03-01"},
    )
    resp = await client.get("/api/v1/papers/rel_paper/outcomes")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ── GET /outcomes/dashboard ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outcomes_dashboard_empty(client):
    resp = await client.get("/api/v1/outcomes/dashboard")
    assert resp.status_code == 200


# ── GET /categories ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_categories_empty(client):
    resp = await client.get("/api/v1/categories")
    assert resp.status_code == 200
    assert resp.json() == []


# ── GET /categories/{slug} ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_category_not_found(client):
    resp = await client.get("/api/v1/categories/nonexistent")
    assert resp.status_code == 404
