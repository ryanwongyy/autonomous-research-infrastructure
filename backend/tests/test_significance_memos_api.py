"""Tests for the significance memos API endpoints (GET/POST /papers/{id}/significance-memo)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating


@pytest_asyncio.fixture
async def memo_data(db_session: AsyncSession):
    """Create a paper (with optional rating) for significance memo tests."""
    family = PaperFamily(
        id="F1", name="Test Family", short_name="TF",
        description="For memo tests", lock_protocol_type="open", active=True,
    )
    db_session.add(family)
    await db_session.flush()

    paper = Paper(
        id="memo_paper", title="Paper for Memo",
        source="ape", family_id="F1", status="published",
        review_status="peer_reviewed",
    )
    db_session.add(paper)
    await db_session.flush()

    rating = Rating(
        paper_id="memo_paper", mu=30.0, sigma=4.0,
        conservative_rating=18.0, elo=1650, matches_played=10,
        rank=3,
    )
    db_session.add(rating)
    await db_session.commit()
    return paper


# -- GET /papers/{paper_id}/significance-memo (no memo yet) --------------------

@pytest.mark.asyncio
async def test_get_memo_none(client, memo_data):
    """Paper with no memo returns null memo."""
    resp = await client.get("/api/v1/papers/memo_paper/significance-memo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "memo_paper"
    assert data["memo"] is None


@pytest.mark.asyncio
async def test_get_memo_nonexistent_paper(client):
    """Nonexistent paper still returns 200 with null memo (no paper validation on GET)."""
    resp = await client.get("/api/v1/papers/nonexistent/significance-memo")
    assert resp.status_code == 200
    assert resp.json()["memo"] is None


# -- POST /papers/{paper_id}/significance-memo ---------------------------------

@pytest.mark.asyncio
async def test_create_memo_submit(client, memo_data):
    resp = await client.post(
        "/api/v1/papers/memo_paper/significance-memo",
        json={
            "author": "Dr. Smith",
            "memo_text": "This paper makes a novel contribution to AI governance.",
            "editorial_verdict": "submit",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "memo_paper"
    assert data["author"] == "Dr. Smith"
    assert data["editorial_verdict"] == "submit"


@pytest.mark.asyncio
async def test_create_memo_hold(client, memo_data):
    resp = await client.post(
        "/api/v1/papers/memo_paper/significance-memo",
        json={
            "author": "Editor A",
            "memo_text": "Needs another round of review.",
            "editorial_verdict": "hold",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["editorial_verdict"] == "hold"


@pytest.mark.asyncio
async def test_create_memo_kill(client, memo_data):
    resp = await client.post(
        "/api/v1/papers/memo_paper/significance-memo",
        json={
            "author": "Editor B",
            "memo_text": "Superseded by newer work.",
            "editorial_verdict": "kill",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["editorial_verdict"] == "kill"


@pytest.mark.asyncio
async def test_create_memo_invalid_verdict(client, memo_data):
    """Invalid verdict should be rejected."""
    resp = await client.post(
        "/api/v1/papers/memo_paper/significance-memo",
        json={
            "author": "Editor C",
            "memo_text": "Some reasoning.",
            "editorial_verdict": "maybe",
        },
    )
    assert resp.status_code == 422  # Pydantic validation (Literal type)


# -- Round-trip: POST then GET -------------------------------------------------

@pytest.mark.asyncio
async def test_memo_round_trip(client, memo_data):
    """Create a memo and verify it shows up on GET."""
    await client.post(
        "/api/v1/papers/memo_paper/significance-memo",
        json={
            "author": "Dr. Jones",
            "memo_text": "Strong empirical contribution.",
            "editorial_verdict": "submit",
        },
    )
    resp = await client.get("/api/v1/papers/memo_paper/significance-memo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["memo"] is not None
    assert data["memo"]["author"] == "Dr. Jones"
    assert data["memo"]["editorial_verdict"] == "submit"
    assert data["memo"]["tournament_rank_at_time"] == 3  # from Rating fixture
