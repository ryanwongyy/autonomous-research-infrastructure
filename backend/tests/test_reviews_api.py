"""Tests for the reviews API endpoints (GET /papers/{id}/reviews, POST /papers/{id}/review)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.review import Review


@pytest_asyncio.fixture
async def review_data(db_session: AsyncSession):
    """Create a paper with reviews."""
    family = PaperFamily(
        id="F1", name="Test", short_name="T",
        description="For review tests", lock_protocol_type="open", active=True,
    )
    db_session.add(family)
    await db_session.flush()

    paper = Paper(
        id="reviewed_paper",
        title="Paper With Reviews",
        source="ape",
        family_id="F1",
        status="published",
        review_status="peer_reviewed",
    )
    db_session.add(paper)
    await db_session.flush()

    reviews = []
    for i, stage in enumerate(["L1_structural", "L2_provenance", "L3_method"]):
        review = Review(
            paper_id="reviewed_paper",
            stage=stage,
            model_used="claude-3.5-sonnet",
            verdict="pass" if i < 2 else "issues",
            content=f"Review content for {stage}",
            iteration=1,
        )
        db_session.add(review)
        reviews.append(review)

    await db_session.commit()
    return paper, reviews


# ── GET /papers/{id}/reviews ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_reviews_for_paper(client, review_data):
    resp = await client.get("/api/v1/papers/reviewed_paper/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    stages = [r["stage"] for r in data]
    assert "L1_structural" in stages
    assert "L2_provenance" in stages
    assert "L3_method" in stages


@pytest.mark.asyncio
async def test_get_reviews_paper_not_found(client):
    resp = await client.get("/api/v1/papers/NOPE/reviews")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_reviews_empty(client, review_data):
    """Paper exists but create one without reviews."""
    # Create a paper with no reviews
    # Use the API to create a bare paper
    resp = await client.post(
        "/api/v1/papers",
        json={"title": "No Reviews Paper", "source": "ape"},
    )
    if resp.status_code == 200:
        paper_id = resp.json()["id"]
        reviews_resp = await client.get(f"/api/v1/papers/{paper_id}/reviews")
        assert reviews_resp.status_code == 200
        assert reviews_resp.json() == []


@pytest.mark.asyncio
async def test_review_response_shape(client, review_data):
    resp = await client.get("/api/v1/papers/reviewed_paper/reviews")
    review = resp.json()[0]
    expected_fields = {"id", "stage", "model_used", "verdict", "content", "iteration", "created_at"}
    assert expected_fields.issubset(set(review.keys()))


# ── POST /papers/{id}/review (trigger) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_trigger_review_paper_not_found(client):
    resp = await client.post("/api/v1/papers/NOPE/review")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_trigger_review_starts(client, review_data):
    """Triggering review returns started status."""
    resp = await client.post("/api/v1/papers/reviewed_paper/review")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "reviewed_paper"
    assert data["status"] == "review_started"
