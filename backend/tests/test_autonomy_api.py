"""Tests for the autonomy API endpoints (GET /papers/{id}/autonomy-card, /families/{id}/autonomy-stats)."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.autonomy_card import AutonomyCard
from app.models.paper import Paper
from app.models.paper_family import PaperFamily


@pytest_asyncio.fixture
async def autonomy_data(db_session: AsyncSession):
    """Create papers with autonomy cards for testing."""
    family = PaperFamily(
        id="F1",
        name="Test Family",
        short_name="TF",
        description="Family for autonomy tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    p1 = Paper(
        id="auto_paper_1",
        title="Fully Autonomous Paper",
        source="ape",
        family_id="F1",
        status="published",
    )
    p2 = Paper(
        id="auto_paper_2",
        title="Mixed Autonomy Paper",
        source="ape",
        family_id="F1",
        status="published",
    )
    p_no_card = Paper(
        id="no_card_paper",
        title="Paper Without Card",
        source="ape",
        family_id="F1",
        status="published",
    )
    db_session.add_all([p1, p2, p_no_card])
    await db_session.flush()

    role_auto = {
        "scout": "full_auto",
        "designer": "full_auto",
        "data_steward": "full_auto",
        "analyst": "full_auto",
        "drafter": "full_auto",
        "verifier": "full_auto",
        "packager": "full_auto",
    }
    card1 = AutonomyCard(
        paper_id="auto_paper_1",
        role_autonomy_json=json.dumps(role_auto),
        human_intervention_points_json=json.dumps([]),
        overall_autonomy_score=1.0,
    )

    role_mixed = {
        "scout": "full_auto",
        "designer": "supervised",
        "data_steward": "full_auto",
        "analyst": "human_driven",
        "drafter": "full_auto",
        "verifier": "full_auto",
        "packager": "full_auto",
    }
    card2 = AutonomyCard(
        paper_id="auto_paper_2",
        role_autonomy_json=json.dumps(role_mixed),
        human_intervention_points_json=json.dumps(
            [
                {"role": "designer", "level": "supervised", "description": "Human reviewed design"},
            ]
        ),
        overall_autonomy_score=0.71,
    )

    db_session.add_all([card1, card2])
    await db_session.commit()
    return {"papers": [p1, p2, p_no_card], "cards": [card1, card2]}


# -- GET /papers/{paper_id}/autonomy-card --------------------------------------


@pytest.mark.asyncio
async def test_paper_autonomy_card(client, autonomy_data):
    resp = await client.get("/api/v1/papers/auto_paper_1/autonomy-card")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "auto_paper_1"
    assert data["card"] is not None
    roles = data["card"]["role_autonomy"]
    assert len(roles) == 7
    assert roles["scout"] == "full_auto"
    assert data["card"]["overall_autonomy_score"] == 1.0


@pytest.mark.asyncio
async def test_paper_autonomy_card_mixed(client, autonomy_data):
    resp = await client.get("/api/v1/papers/auto_paper_2/autonomy-card")
    assert resp.status_code == 200
    data = resp.json()
    card = data["card"]
    assert card["role_autonomy"]["designer"] == "supervised"
    assert card["role_autonomy"]["analyst"] == "human_driven"
    assert len(card["human_intervention_points"]) == 1


@pytest.mark.asyncio
async def test_paper_autonomy_no_card(client, autonomy_data):
    """Paper exists but has no autonomy card — returns null card."""
    resp = await client.get("/api/v1/papers/no_card_paper/autonomy-card")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "no_card_paper"
    assert data["card"] is None


@pytest.mark.asyncio
async def test_paper_autonomy_nonexistent(client):
    """Nonexistent paper — still returns 200 with null card (no paper validation)."""
    resp = await client.get("/api/v1/papers/nonexistent/autonomy-card")
    assert resp.status_code == 200
    assert resp.json()["card"] is None


# -- GET /families/{family_id}/autonomy-stats ----------------------------------


@pytest.mark.asyncio
async def test_family_autonomy_stats(client, autonomy_data):
    resp = await client.get("/api/v1/families/F1/autonomy-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["family_id"] == "F1"
    assert data["total_papers"] == 2
    assert data["avg_autonomy_score"] > 0
    assert "role_breakdown" in data
    breakdown = data["role_breakdown"]
    assert "scout" in breakdown
    assert breakdown["scout"]["full_auto"] == 2


@pytest.mark.asyncio
async def test_family_autonomy_stats_empty(client):
    """Family with no papers/cards — returns zero stats."""
    resp = await client.get("/api/v1/families/nonexistent/autonomy-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_papers"] == 0
    assert data["avg_autonomy_score"] == 0.0
