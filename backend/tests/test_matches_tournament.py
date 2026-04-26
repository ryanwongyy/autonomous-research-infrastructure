"""Tests for matches and tournament API endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper_family import PaperFamily
from app.models.tournament_run import TournamentRun


@pytest_asyncio.fixture
async def tournament_data(db_session: AsyncSession):
    """Create a family and a tournament run."""
    family = PaperFamily(
        id="F1", name="Test", short_name="T",
        description="For tournament tests", lock_protocol_type="open", active=True,
    )
    db_session.add(family)
    await db_session.flush()

    run = TournamentRun(
        family_id="F1",
        status="completed",
        total_matches=10,
        total_batches=2,
        papers_in_pool=5,
        benchmark_papers=2,
        ai_papers=3,
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run


# ── GET /matches ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_matches_empty(client):
    resp = await client.get("/api/v1/matches")
    assert resp.status_code == 200
    assert resp.json() == []


# ── GET /matches/{match_id} ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_match_not_found(client):
    resp = await client.get("/api/v1/matches/99999")
    assert resp.status_code == 404


# ── GET /tournament/runs ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_tournament_runs_empty(client):
    resp = await client.get("/api/v1/tournament/runs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_tournament_runs(client, tournament_data):
    resp = await client.get("/api/v1/tournament/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "completed"
    assert data[0]["family_id"] == "F1"
    assert data[0]["total_matches"] == 10


@pytest.mark.asyncio
async def test_list_tournament_runs_filter_by_family(client, tournament_data):
    resp = await client.get("/api/v1/tournament/runs?family_id=F1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp2 = await client.get("/api/v1/tournament/runs?family_id=NOPE")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 0


# ── GET /tournament/runs/{run_id} ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_tournament_run_not_found(client):
    resp = await client.get("/api/v1/tournament/runs/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_tournament_run_detail(client, tournament_data):
    run_id = tournament_data.id
    resp = await client.get(f"/api/v1/tournament/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run_id
    assert data["family"]["short_name"] == "T"
    assert data["matches"] == []  # no matches created in fixture


# ── POST /tournament/run (auth required) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tournament_run_requires_admin(client, monkeypatch):
    """Tournament trigger requires admin key."""
    monkeypatch.setattr("app.config.settings.ape_api_key", "key")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "admin")
    resp = await client.post(
        "/api/v1/tournament/run?family_id=F1",
        headers={"X-API-Key": "key"},
    )
    assert resp.status_code == 403
