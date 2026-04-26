"""Tests for the families API endpoints."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_families(db_session: AsyncSession):
    """Insert two families into the test database."""
    fam1 = PaperFamily(
        id="F1",
        name="Federal AI Procurement Governance",
        short_name="Fed-Proc",
        description="Studies federal procurement rules for AI systems",
        lock_protocol_type="venue-lock",
        venue_ladder=json.dumps({"flagship": ["AJPS", "JOP"], "elite_field": []}),
        mandatory_checks=json.dumps(["data_provenance", "method_replication"]),
        fatal_failures=json.dumps(["fabrication"]),
        elite_ceiling="Top-decile methodological novelty",
        max_portfolio_share=0.33,
        active=True,
    )
    fam2 = PaperFamily(
        id="F2",
        name="International AI Coordination Mechanisms",
        short_name="Intl-Coord",
        description="Examines cross-border AI governance coordination",
        lock_protocol_type="method-lock",
        active=True,
    )
    fam_inactive = PaperFamily(
        id="F99",
        name="Inactive Family",
        short_name="Inactive",
        description="This family is not active",
        lock_protocol_type="open",
        active=False,
    )
    db_session.add_all([fam1, fam2, fam_inactive])
    await db_session.commit()
    return [fam1, fam2, fam_inactive]


@pytest_asyncio.fixture
async def family_with_papers(db_session: AsyncSession, seeded_families):
    """Add papers to family F1."""
    papers = [
        Paper(
            id=f"paper_{i}",
            title=f"Test Paper {i}",
            source="ape",
            family_id="F1",
            status="published",
        )
        for i in range(3)
    ]
    db_session.add_all(papers)
    await db_session.commit()
    return papers


# ── GET /families ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_families_empty(client):
    """Empty database returns empty family list."""
    resp = await client.get("/api/v1/families")
    assert resp.status_code == 200
    data = resp.json()
    assert data["families"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_families_active_only(client, seeded_families):
    """Default active_only=True excludes inactive families."""
    resp = await client.get("/api/v1/families")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    family_ids = [f["id"] for f in data["families"]]
    assert "F1" in family_ids
    assert "F2" in family_ids
    assert "F99" not in family_ids  # inactive


@pytest.mark.asyncio
async def test_list_families_include_inactive(client, seeded_families):
    """active_only=false includes inactive families."""
    resp = await client.get("/api/v1/families?active_only=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    family_ids = [f["id"] for f in data["families"]]
    assert "F99" in family_ids


@pytest.mark.asyncio
async def test_list_families_paper_count(client, family_with_papers):
    """Paper count is correctly aggregated per family."""
    resp = await client.get("/api/v1/families")
    assert resp.status_code == 200
    families = {f["id"]: f for f in resp.json()["families"]}
    assert families["F1"]["paper_count"] == 3
    assert families["F2"]["paper_count"] == 0


@pytest.mark.asyncio
async def test_list_families_response_shape(client, seeded_families):
    """Each family has the expected fields."""
    resp = await client.get("/api/v1/families")
    fam = resp.json()["families"][0]
    expected_keys = {
        "id", "name", "short_name", "description", "lock_protocol_type",
        "venue_ladder", "mandatory_checks", "fatal_failures",
        "elite_ceiling", "max_portfolio_share", "paper_count", "active",
    }
    assert expected_keys.issubset(set(fam.keys()))


@pytest.mark.asyncio
async def test_list_families_venue_ladder_parsed(client, seeded_families):
    """JSON-encoded venue_ladder is returned as an object, not a string."""
    resp = await client.get("/api/v1/families")
    fam_f1 = next(f for f in resp.json()["families"] if f["id"] == "F1")
    assert isinstance(fam_f1["venue_ladder"], dict)
    assert "flagship" in fam_f1["venue_ladder"]


# ── GET /families/{family_id} ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_family_detail(client, seeded_families):
    """Get a specific family by ID returns full detail."""
    resp = await client.get("/api/v1/families/F1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "F1"
    assert data["name"] == "Federal AI Procurement Governance"
    assert data["lock_protocol_type"] == "venue-lock"
    assert "funnel_stages" in data
    assert isinstance(data["funnel_stages"], dict)


@pytest.mark.asyncio
async def test_get_family_detail_includes_extra_fields(client, seeded_families):
    """Detail endpoint includes fields not in the list endpoint."""
    resp = await client.get("/api/v1/families/F1")
    data = resp.json()
    detail_fields = {"canonical_questions", "accepted_methods", "public_data_sources",
                     "novelty_threshold", "benchmark_config", "review_rubric", "funnel_stages"}
    assert detail_fields.issubset(set(data.keys()))


@pytest.mark.asyncio
async def test_get_family_with_papers_funnel(client, family_with_papers):
    """Funnel stages reflect actual paper distribution."""
    resp = await client.get("/api/v1/families/F1")
    data = resp.json()
    # All 3 papers have default funnel_stage="idea"
    assert data["funnel_stages"].get("idea", 0) == 3


@pytest.mark.asyncio
async def test_get_family_not_found(client):
    """Nonexistent family returns 404."""
    resp = await client.get("/api/v1/families/NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_inactive_family(client, seeded_families):
    """Inactive families are still accessible by direct ID."""
    resp = await client.get("/api/v1/families/F99")
    assert resp.status_code == 200
    assert resp.json()["active"] is False
