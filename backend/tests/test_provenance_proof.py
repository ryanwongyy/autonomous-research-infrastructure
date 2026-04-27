"""Tests for Step 2 provenance proof — SourceSnapshot.provenance_proof_json
and L2 enforcement.

The "real data, real claims" bar requires every public paper's claims to be
traceable to source snapshots that were produced by a real HTTP fetch.
This file tests:
  - The SourceSnapshot model carries the provenance_proof_json column.
  - The data_steward populates it when a real fetch succeeds.
  - L2 Provenance rejects claims tied to snapshots without a proof, with a
    placeholder proof, or with a malformed proof.
  - L2 Provenance accepts claims tied to snapshots with method="http"/"vcr".
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_map import ClaimMap
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.services.review_pipeline.l2_provenance import _check_provenance_proofs

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def paper_with_snapshot(db_session: AsyncSession):
    """Create a Paper, SourceCard, SourceSnapshot, and ClaimMap. The
    snapshot's provenance_proof_json starts as None; tests set it as needed.
    """
    family = PaperFamily(
        id="F_PROOF",
        name="Test Family",
        short_name="TestF",
        description="for proof tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    paper = Paper(
        id="paper_proof_1",
        title="Proof Test Paper",
        family_id="F_PROOF",
        source="ape",
        status="published",
    )
    db_session.add(paper)

    source_card = SourceCard(
        id="src_test_proof",
        name="Test Source",
        url="https://example.com/test",
        tier="A",
        source_type="api",
        access_method="api",
        legal_basis="public domain",
        claim_permissions=json.dumps(["any"]),
        claim_prohibitions=json.dumps([]),
        content_hash="0" * 64,
    )
    db_session.add(source_card)
    await db_session.flush()

    snapshot = SourceSnapshot(
        source_card_id=source_card.id,
        snapshot_hash="0" * 64,
        snapshot_path="/tmp/test_snapshot",
        file_size_bytes=100,
        record_count=10,
        fetched_at=datetime.now(UTC),
        provenance_proof_json=None,  # tests set this directly
    )
    db_session.add(snapshot)
    await db_session.flush()

    claim = ClaimMap(
        paper_id=paper.id,
        claim_text="A test claim sourced from the snapshot.",
        claim_type="empirical",
        source_card_id=source_card.id,
        source_snapshot_id=snapshot.id,
        verification_status="verified",
    )
    db_session.add(claim)
    await db_session.commit()

    return {
        "paper": paper,
        "snapshot": snapshot,
        "claim": claim,
        "source_card": source_card,
    }


# ── Schema ────────────────────────────────────────────────────────────────────


def test_source_snapshot_has_provenance_proof_column():
    """The model exposes the new column; downstream code can read/write it."""
    assert hasattr(SourceSnapshot, "provenance_proof_json")


# ── L2 enforcement: reject snapshots without proof ───────────────────────────


@pytest.mark.asyncio
async def test_l2_rejects_snapshot_with_null_proof(db_session, paper_with_snapshot):
    """A claim tied to a snapshot with no provenance proof → critical issue."""
    paper = paper_with_snapshot["paper"]
    issues = await _check_provenance_proofs(db_session, paper.id)
    assert len(issues) == 1
    assert issues[0]["check"] == "provenance_proof_missing"
    assert issues[0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_l2_rejects_placeholder_proof(db_session, paper_with_snapshot):
    """DATA_MODE=permissive emits {"method": "placeholder"}; L2 rejects it."""
    snapshot: SourceSnapshot = paper_with_snapshot["snapshot"]
    snapshot.provenance_proof_json = json.dumps(
        {
            "method": "placeholder",
            "source_id": "src_test_proof",
            "fetch_error": "no API key",
        }
    )
    db_session.add(snapshot)
    await db_session.commit()

    issues = await _check_provenance_proofs(db_session, paper_with_snapshot["paper"].id)
    assert len(issues) == 1
    assert issues[0]["check"] == "provenance_proof_synthetic"
    assert issues[0]["severity"] == "critical"
    assert issues[0]["proof_method"] == "placeholder"


@pytest.mark.asyncio
async def test_l2_rejects_unknown_method(db_session, paper_with_snapshot):
    """Any method other than http/vcr is rejected — defends against future
    drift if someone adds a new permissive method."""
    snapshot: SourceSnapshot = paper_with_snapshot["snapshot"]
    snapshot.provenance_proof_json = json.dumps({"method": "manual_upload", "source_id": "x"})
    db_session.add(snapshot)
    await db_session.commit()

    issues = await _check_provenance_proofs(db_session, paper_with_snapshot["paper"].id)
    assert len(issues) == 1
    assert issues[0]["check"] == "provenance_proof_synthetic"
    assert issues[0]["proof_method"] == "manual_upload"


@pytest.mark.asyncio
async def test_l2_rejects_malformed_proof_json(db_session, paper_with_snapshot):
    """Garbage JSON is treated as a critical issue, not silently accepted."""
    snapshot: SourceSnapshot = paper_with_snapshot["snapshot"]
    snapshot.provenance_proof_json = "{not valid json"
    db_session.add(snapshot)
    await db_session.commit()

    issues = await _check_provenance_proofs(db_session, paper_with_snapshot["paper"].id)
    assert len(issues) == 1
    assert issues[0]["check"] == "provenance_proof_malformed"


# ── L2 enforcement: accept real proofs ────────────────────────────────────────


@pytest.mark.asyncio
async def test_l2_accepts_http_proof(db_session, paper_with_snapshot):
    """A real-HTTP proof passes L2 with no issues."""
    snapshot: SourceSnapshot = paper_with_snapshot["snapshot"]
    snapshot.provenance_proof_json = json.dumps(
        {
            "method": "http",
            "request_url": "https://api.example.com/v1/data?q=test",
            "response_status": 200,
            "response_hash": "a" * 64,
            "fetched_at": datetime.now(UTC).isoformat(),
            "fetched_via": "test_client_v1",
        }
    )
    db_session.add(snapshot)
    await db_session.commit()

    issues = await _check_provenance_proofs(db_session, paper_with_snapshot["paper"].id)
    assert issues == []


@pytest.mark.asyncio
async def test_l2_accepts_vcr_proof(db_session, paper_with_snapshot):
    """VCR-cassette proofs (used in offline tests) are also accepted."""
    snapshot: SourceSnapshot = paper_with_snapshot["snapshot"]
    snapshot.provenance_proof_json = json.dumps(
        {
            "method": "vcr",
            "request_url": "https://api.example.com/v1/data?q=test",
            "response_status": 200,
            "response_hash": "b" * 64,
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "fetched_via": "test_cassette",
        }
    )
    db_session.add(snapshot)
    await db_session.commit()

    issues = await _check_provenance_proofs(db_session, paper_with_snapshot["paper"].id)
    assert issues == []


# ── make_http_proof helper ────────────────────────────────────────────────────


def test_make_http_proof_shape():
    """Helper produces the documented dict shape that data_steward writes
    to the snapshot and L2 reads back."""
    from app.services.data_sources.base import make_http_proof

    proof = make_http_proof(
        request_url="https://api.example.com/v1/x?y=1",
        response_status=200,
        response_body=b"hello world",
        fetched_via="example_client_v1",
    )

    assert proof["method"] == "http"
    assert proof["request_url"] == "https://api.example.com/v1/x?y=1"
    assert proof["response_status"] == 200
    # SHA-256 of "hello world"
    assert (
        proof["response_hash"] == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )
    assert proof["fetched_via"] == "example_client_v1"
    # ISO 8601 with timezone
    assert "T" in proof["fetched_at"]
    assert proof["fetched_at"].endswith("+00:00")


# ── data_steward integration ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_data_steward_writes_placeholder_proof_in_permissive_mode(db_session, monkeypatch):
    """End-to-end: in permissive mode, fetch_and_snapshot creates a snapshot
    whose provenance_proof_json marks it as a placeholder. L2 then rejects it.
    """
    monkeypatch.setattr(
        "app.services.paper_generation.data_fetcher.settings.data_mode",
        "permissive",
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.data_steward.settings.data_mode",
        "permissive",
    )

    family = PaperFamily(
        id="F_DS",
        name="Data Steward Test",
        short_name="DS",
        description="test",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)

    paper = Paper(
        id="paper_ds_1",
        title="DS Test Paper",
        family_id="F_DS",
        source="ape",
        status="draft",
        funnel_stage="locked",
    )
    db_session.add(paper)

    source_card = SourceCard(
        id="nonexistent_source_for_test",
        name="No-Such Source",
        url="https://example.invalid",
        tier="C",
        source_type="api",
        access_method="api",
        legal_basis="public domain",
        claim_permissions=json.dumps([]),
        claim_prohibitions=json.dumps([]),
        content_hash="0" * 64,
    )
    db_session.add(source_card)
    await db_session.commit()

    from app.services.paper_generation.roles.data_steward import fetch_and_snapshot

    snapshot = await fetch_and_snapshot(
        db_session,
        paper_id="paper_ds_1",
        source_id="nonexistent_source_for_test",
    )
    await db_session.commit()

    assert snapshot.provenance_proof_json is not None
    proof = json.loads(snapshot.provenance_proof_json)
    assert proof["method"] == "placeholder"
    assert proof["source_id"] == "nonexistent_source_for_test"
