"""Tests for provenance API endpoints (claims, provenance report, claim verification)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_map import ClaimMap
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot


@pytest_asyncio.fixture
async def provenance_data(db_session: AsyncSession):
    """Create paper, source card, claims, and optional snapshots for provenance tests."""
    family = PaperFamily(
        id="F1",
        name="Test Family",
        short_name="TF",
        description="For provenance tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    paper = Paper(
        id="prov_paper",
        title="Paper with Claims",
        source="ape",
        family_id="F1",
        status="published",
    )
    paper_empty = Paper(
        id="prov_empty",
        title="Paper with No Claims",
        source="ape",
        family_id="F1",
        status="published",
    )
    db_session.add_all([paper, paper_empty])
    await db_session.flush()

    source = SourceCard(
        id="fed_register",
        name="Federal Register",
        url="https://www.federalregister.gov",
        tier="A",
        source_type="government",
        update_frequency="daily",
        access_method="api",
        requires_key=False,
        canonical_unit="rule",
        claim_permissions='["regulatory_text"]',
        claim_prohibitions='["draft_rules"]',
        fragility_score=0.1,
        active=True,
    )
    db_session.add(source)
    await db_session.flush()

    snapshot = SourceSnapshot(
        source_card_id="fed_register",
        snapshot_hash="abc123def456",
        snapshot_path="/snapshots/fed_register/2026-04-01.json",
        file_size_bytes=50000,
        record_count=120,
    )
    db_session.add(snapshot)
    await db_session.flush()

    # Claim 1: pending, linked to source + snapshot (will verify as true)
    claim1 = ClaimMap(
        paper_id="prov_paper",
        claim_text="AI regulation requires transparency mandates",
        claim_type="doctrinal",
        source_card_id="fed_register",
        source_snapshot_id=snapshot.id,
        verification_status="pending",
    )
    # Claim 2: pending, linked to source but no snapshot (will fail verification)
    claim2 = ClaimMap(
        paper_id="prov_paper",
        claim_text="Enforcement actions increased 30% in 2025",
        claim_type="empirical",
        source_card_id="fed_register",
        source_snapshot_id=None,
        verification_status="pending",
    )
    # Claim 3: already verified
    claim3 = ClaimMap(
        paper_id="prov_paper",
        claim_text="Historical precedent shows gradual adoption",
        claim_type="historical",
        verification_status="verified",
        verified_by="auto:provenance_check",
        result_object_ref='{"analysis_run_id": "run_1", "table": "t1"}',
    )
    db_session.add_all([claim1, claim2, claim3])
    await db_session.commit()
    return {
        "paper": paper,
        "paper_empty": paper_empty,
        "source": source,
        "snapshot": snapshot,
        "claims": [claim1, claim2, claim3],
    }


# -- GET /papers/{paper_id}/claims --------------------------------------------


@pytest.mark.asyncio
async def test_list_claims(client, provenance_data):
    resp = await client.get("/api/v1/papers/prov_paper/claims")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "prov_paper"
    assert data["total"] == 3
    assert len(data["claims"]) == 3
    assert "status_summary" in data


@pytest.mark.asyncio
async def test_list_claims_empty(client, provenance_data):
    resp = await client.get("/api/v1/papers/prov_empty/claims")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["claims"] == []


@pytest.mark.asyncio
async def test_list_claims_paper_not_found(client):
    resp = await client.get("/api/v1/papers/nonexistent/claims")
    assert resp.status_code == 404


# -- GET /papers/{paper_id}/provenance -----------------------------------------


@pytest.mark.asyncio
async def test_provenance_report(client, provenance_data):
    resp = await client.get("/api/v1/papers/prov_paper/provenance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "prov_paper"
    assert data["paper_title"] == "Paper with Claims"
    assert data["claim_coverage"]["total_claims"] == 3
    assert data["claim_coverage"]["coverage_ratio"] > 0
    assert "verified" in data["verification_status"]
    assert "tier_compliance" in data
    assert "source_freshness" in data
    assert isinstance(data["provenance_complete"], bool)


@pytest.mark.asyncio
async def test_provenance_report_empty_paper(client, provenance_data):
    resp = await client.get("/api/v1/papers/prov_empty/provenance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["claim_coverage"]["total_claims"] == 0
    assert data["claim_coverage"]["coverage_ratio"] == 0.0
    # No claims means provenance is not complete (total_claims == 0)
    assert data["provenance_complete"] is False


@pytest.mark.asyncio
async def test_provenance_not_found(client):
    resp = await client.get("/api/v1/papers/nonexistent/provenance")
    assert resp.status_code == 404


# -- POST /papers/{paper_id}/claims/verify ------------------------------------


@pytest.mark.asyncio
async def test_verify_claims(client, provenance_data):
    """Verification should process pending claims."""
    resp = await client.post("/api/v1/papers/prov_paper/claims/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "prov_paper"
    assert data["message"] == "Claim verification complete"
    # claim1 has snapshot with hash → verified; claim2 has source but no snapshot → skipped
    assert data["verified"] >= 1


@pytest.mark.asyncio
async def test_verify_claims_idempotent(client, provenance_data):
    """Running verify twice: second run verifies fewer claims (already-verified are not pending)."""
    first = await client.post("/api/v1/papers/prov_paper/claims/verify")
    first_data = first.json()
    verified_first = first_data["verified"]

    second = await client.post("/api/v1/papers/prov_paper/claims/verify")
    assert second.status_code == 200
    second_data = second.json()
    # Claims verified in first run are no longer pending — fewer verified on second pass
    assert second_data["verified"] <= verified_first


@pytest.mark.asyncio
async def test_verify_claims_not_found(client):
    resp = await client.post("/api/v1/papers/nonexistent/claims/verify")
    assert resp.status_code == 404
