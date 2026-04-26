"""Tests for the release API endpoints (not the service layer — that's in test_release.py)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily


@pytest_asyncio.fixture
async def release_papers(db_session: AsyncSession):
    """Create papers at various release stages."""
    family = PaperFamily(
        id="F1", name="Test", short_name="T",
        description="For release tests", lock_protocol_type="open", active=True,
    )
    db_session.add(family)
    await db_session.flush()

    internal = Paper(
        id="rel_internal", title="Internal Paper", source="ape",
        family_id="F1", status="published", release_status="internal",
        review_status="peer_reviewed",
    )
    candidate = Paper(
        id="rel_candidate", title="Candidate Paper", source="ape",
        family_id="F1", status="published", release_status="candidate",
        review_status="peer_reviewed",
    )
    db_session.add_all([internal, candidate])
    await db_session.commit()
    return {"internal": internal, "candidate": candidate}


# ── GET /release/status ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_release_status_overview_empty(client):
    resp = await client.get("/api/v1/release/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_release_status_with_data(client, release_papers):
    resp = await client.get("/api/v1/release/status")
    assert resp.status_code == 200
    data = resp.json()
    # Should have counts for internal and candidate stages
    assert isinstance(data, dict)


# ── GET /papers/{id}/release ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_paper_release_status(client, release_papers):
    resp = await client.get("/api/v1/papers/rel_internal/release")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "rel_internal"
    assert data["release_status"] == "internal"


@pytest.mark.asyncio
async def test_paper_release_not_found(client):
    resp = await client.get("/api/v1/papers/NOPE/release")
    assert resp.status_code == 404


# ── GET /papers/{id}/release/preconditions ────────────────────────────────────

@pytest.mark.asyncio
async def test_preconditions_check(client, release_papers):
    resp = await client.get("/api/v1/papers/rel_internal/release/preconditions?target_status=candidate")
    assert resp.status_code == 200
    data = resp.json()
    assert "can_transition" in data


@pytest.mark.asyncio
async def test_preconditions_not_found(client):
    resp = await client.get("/api/v1/papers/NOPE/release/preconditions?target_status=candidate")
    assert resp.status_code == 404


# ── POST /papers/{id}/release/transition ──────────────────────────────────────

@pytest.mark.asyncio
async def test_transition_not_found(client):
    resp = await client.post("/api/v1/papers/NOPE/release/transition?target_status=candidate")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_transition_force_requires_approved_by(client, release_papers):
    """Force transition without approved_by should fail."""
    resp = await client.post(
        "/api/v1/papers/rel_internal/release/transition?target_status=candidate&force=true"
    )
    assert resp.status_code == 400
    assert "approved_by" in resp.json()["detail"]
