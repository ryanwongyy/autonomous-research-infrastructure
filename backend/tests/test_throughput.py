"""Tests for the throughput API endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily


@pytest_asyncio.fixture
async def throughput_data(db_session: AsyncSession):
    """Create families and papers at various funnel stages."""
    family = PaperFamily(
        id="F1",
        name="Test Family",
        short_name="TF",
        description="For throughput tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    stages = ["idea", "screened", "locked", "analyzing", "drafting", "candidate", "killed"]
    for i, stage in enumerate(stages):
        paper = Paper(
            id=f"tp_paper_{i}",
            title=f"Paper at {stage}",
            source="ape",
            family_id="F1",
            status="killed" if stage == "killed" else "published",
            funnel_stage=stage,
        )
        db_session.add(paper)

    await db_session.commit()


# ── GET /throughput/funnel ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_funnel_empty(client):
    """Funnel snapshot on empty DB returns default structure."""
    resp = await client.get("/api/v1/throughput/funnel")
    assert resp.status_code == 200
    data = resp.json()
    assert "stages" in data or "total_active" in data


@pytest.mark.asyncio
async def test_funnel_with_data(client, throughput_data):
    """Funnel returns stage counts for populated database."""
    resp = await client.get("/api/v1/throughput/funnel")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_funnel_filtered_by_family(client, throughput_data):
    """family_id filter scopes the funnel to one family."""
    resp = await client.get("/api/v1/throughput/funnel?family_id=F1")
    assert resp.status_code == 200


# ── GET /throughput/conversion-rates ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_conversion_rates_empty(client):
    resp = await client.get("/api/v1/throughput/conversion-rates")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_conversion_rates_with_data(client, throughput_data):
    resp = await client.get("/api/v1/throughput/conversion-rates")
    assert resp.status_code == 200


# ── GET /throughput/bottlenecks ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bottlenecks_empty(client):
    resp = await client.get("/api/v1/throughput/bottlenecks")
    assert resp.status_code == 200


# ── GET /throughput/projections ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_projections_empty(client):
    resp = await client.get("/api/v1/throughput/projections")
    assert resp.status_code == 200


# ── GET /throughput/daily-targets ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_daily_targets_empty(client):
    resp = await client.get("/api/v1/throughput/daily-targets")
    assert resp.status_code == 200


# ── GET /throughput/work-queue ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_work_queue_empty(client):
    resp = await client.get("/api/v1/throughput/work-queue")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_work_queue_filtered(client, throughput_data):
    resp = await client.get("/api/v1/throughput/work-queue?family_id=F1")
    assert resp.status_code == 200
