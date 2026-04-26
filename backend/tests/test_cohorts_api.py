"""Tests for the cohorts API endpoints (GET /cohorts, /cohorts/{id}, /papers/{id}/cohort)."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohort_tag import CohortTag
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating


@pytest_asyncio.fixture
async def cohort_data(db_session: AsyncSession):
    """Create papers with cohort tags and ratings for testing."""
    family = PaperFamily(
        id="F1", name="Test Family", short_name="TF",
        description="For cohort tests", lock_protocol_type="open", active=True,
    )
    db_session.add(family)
    await db_session.flush()

    p1 = Paper(
        id="cohort_p1", title="Paper 1 Q1",
        source="ape", family_id="F1", status="published",
    )
    p2 = Paper(
        id="cohort_p2", title="Paper 2 Q1",
        source="ape", family_id="F1", status="published",
    )
    p3 = Paper(
        id="cohort_p3", title="Paper 3 Q2",
        source="ape", family_id="F1", status="published",
    )
    p_no_cohort = Paper(
        id="no_cohort_paper", title="Untagged Paper",
        source="ape", family_id="F1", status="draft",
    )
    db_session.add_all([p1, p2, p3, p_no_cohort])
    await db_session.flush()

    tag1 = CohortTag(
        paper_id="cohort_p1", cohort_id="2026-Q1-opus4",
        generation_model="claude-opus-4-6",
        review_models_json=json.dumps(["gemini-2.0-flash"]),
        tournament_judge_model="gemini-2.0-flash",
    )
    tag2 = CohortTag(
        paper_id="cohort_p2", cohort_id="2026-Q1-opus4",
        generation_model="claude-opus-4-6",
    )
    tag3 = CohortTag(
        paper_id="cohort_p3", cohort_id="2026-Q2-gpt4o",
        generation_model="gpt-4o",
    )
    db_session.add_all([tag1, tag2, tag3])
    await db_session.flush()

    # Add ratings so cohort comparison has data
    r1 = Rating(
        paper_id="cohort_p1", mu=28.0, sigma=5.0,
        conservative_rating=13.0, elo=1600, matches_played=5,
    )
    r2 = Rating(
        paper_id="cohort_p2", mu=22.0, sigma=7.0,
        conservative_rating=1.0, elo=1400, matches_played=3,
    )
    db_session.add_all([r1, r2])
    await db_session.commit()
    return {"papers": [p1, p2, p3, p_no_cohort], "tags": [tag1, tag2, tag3]}


# -- GET /cohorts --------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_cohorts_empty(client):
    resp = await client.get("/api/v1/cohorts")
    assert resp.status_code == 200
    data = resp.json()
    assert "cohorts" in data
    assert data["cohorts"] == []


@pytest.mark.asyncio
async def test_list_cohorts(client, cohort_data):
    resp = await client.get("/api/v1/cohorts")
    assert resp.status_code == 200
    data = resp.json()
    cohorts = data["cohorts"]
    assert len(cohorts) == 2
    ids = {c["cohort_id"] for c in cohorts}
    assert "2026-Q1-opus4" in ids
    assert "2026-Q2-gpt4o" in ids


@pytest.mark.asyncio
async def test_list_cohorts_has_metrics(client, cohort_data):
    resp = await client.get("/api/v1/cohorts")
    q1 = next(c for c in resp.json()["cohorts"] if c["cohort_id"] == "2026-Q1-opus4")
    assert q1["paper_count"] == 2
    assert q1["generation_model"] == "claude-opus-4-6"
    assert q1["rated_papers"] == 2
    assert q1["avg_mu"] == 25.0  # (28 + 22) / 2


# -- GET /cohorts/{cohort_id} --------------------------------------------------

@pytest.mark.asyncio
async def test_get_cohort_detail(client, cohort_data):
    resp = await client.get("/api/v1/cohorts/2026-Q1-opus4")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cohort_id"] == "2026-Q1-opus4"
    assert data["metrics"] is not None
    assert data["metrics"]["paper_count"] == 2


@pytest.mark.asyncio
async def test_get_cohort_not_found(client):
    resp = await client.get("/api/v1/cohorts/nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["metrics"] is None


# -- GET /papers/{paper_id}/cohort ---------------------------------------------

@pytest.mark.asyncio
async def test_paper_cohort(client, cohort_data):
    resp = await client.get("/api/v1/papers/cohort_p1/cohort")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "cohort_p1"
    assert data["cohort"]["cohort_id"] == "2026-Q1-opus4"
    assert data["cohort"]["generation_model"] == "claude-opus-4-6"


@pytest.mark.asyncio
async def test_paper_cohort_no_tag(client, cohort_data):
    """Paper without a cohort tag returns null cohort."""
    resp = await client.get("/api/v1/papers/no_cohort_paper/cohort")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "no_cohort_paper"
    assert data["cohort"] is None
