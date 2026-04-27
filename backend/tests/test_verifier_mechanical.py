"""Step 3 tests: mechanical claim verification in the Verifier role.

The Verifier no longer relies solely on LLM judgement to decide whether a
claim is supported. Before the LLM is consulted, every claim that cites a
SourceSnapshot is mechanically checked:
  - The snapshot bytes must be retrievable from the artifact store.
  - If ``source_span_ref`` carries a ``quote`` field, that quote must be a
    substring of the snapshot bytes.

Mechanical failures override any LLM verdict (`overall = "fail"`,
`recommendation = "reject"`).
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
from app.services.paper_generation.roles.verifier import (
    _apply_mechanical_failures,
    _mechanical_verify_claims,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def setup_paper_with_snapshot(db_session: AsyncSession, monkeypatch, tmp_path):
    """Build a Paper + SourceCard + SourceSnapshot with real bytes in a
    temporary content-addressed store. Tests then create ClaimMaps citing
    the snapshot and assert mechanical verification behaviour.
    """
    # Point the store at a clean tmp dir for each test.
    monkeypatch.setattr("app.config.settings.artifact_store_path", str(tmp_path))

    family = PaperFamily(
        id="F_VERIFIER",
        name="Verifier Test",
        short_name="VT",
        description="for mechanical verifier tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    paper = Paper(
        id="paper_verifier_1",
        title="Verifier Test Paper",
        family_id="F_VERIFIER",
        source="ape",
        status="draft",
    )
    db_session.add(paper)

    source_card = SourceCard(
        id="src_verifier",
        name="Verifier Test Source",
        url="https://example.com/v",
        tier="A",
        source_type="api",
        access_method="api",
        legal_basis="public",
        claim_permissions=json.dumps(["any"]),
        claim_prohibitions=json.dumps([]),
        content_hash="0" * 64,
    )
    db_session.add(source_card)
    await db_session.flush()

    # Real bytes that will be stored in the artifact store. Tests assert
    # quotes are matched against THIS exact text.
    snapshot_text = (
        "The agency reported that 42 firms were affected. The total cost was $5.7 billion."
    )
    snapshot_bytes = snapshot_text.encode("utf-8")

    # Persist to the (tmp) artifact store using the same hashing / layout
    # as production code.
    from app.services.provenance.hasher import hash_content
    from app.services.storage.artifact_store import FilesystemArtifactStore

    store = FilesystemArtifactStore(str(tmp_path))
    content_hash = hash_content(snapshot_bytes)
    await store.store(snapshot_bytes, artifact_type="source_snapshot")

    snapshot = SourceSnapshot(
        source_card_id=source_card.id,
        snapshot_hash=content_hash,
        snapshot_path=str(store._hash_path(content_hash)),
        file_size_bytes=len(snapshot_bytes),
        record_count=1,
        fetched_at=datetime.now(UTC),
        provenance_proof_json=json.dumps(
            {
                "method": "http",
                "request_url": "https://example.com/v?q=test",
                "response_status": 200,
                "response_hash": content_hash,
                "fetched_at": datetime.now(UTC).isoformat(),
                "fetched_via": "test_v1",
            }
        ),
    )
    db_session.add(snapshot)
    await db_session.commit()

    return {
        "paper": paper,
        "source_card": source_card,
        "snapshot": snapshot,
        "snapshot_text": snapshot_text,
        "snapshot_bytes": snapshot_bytes,
    }


# ── _mechanical_verify_claims ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_snapshot_reference_skipped(db_session, setup_paper_with_snapshot):
    """A claim without ``source_snapshot_id`` is skipped (left to the LLM)."""
    paper = setup_paper_with_snapshot["paper"]
    claim = ClaimMap(
        paper_id=paper.id,
        claim_text="Theoretical claim with no source snapshot.",
        claim_type="theoretical",
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [claim])
    assert failures == {}


@pytest.mark.asyncio
async def test_quote_present_passes(db_session, setup_paper_with_snapshot):
    """A claim whose quote appears verbatim in the snapshot bytes passes."""
    paper = setup_paper_with_snapshot["paper"]
    snapshot = setup_paper_with_snapshot["snapshot"]
    claim = ClaimMap(
        paper_id=paper.id,
        claim_text="The agency reported 42 firms affected.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref=json.dumps({"quote": "42 firms were affected"}),
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [claim])
    assert failures == {}


@pytest.mark.asyncio
async def test_quote_absent_fails(db_session, setup_paper_with_snapshot):
    """A fabricated quote → mechanical failure with informative reason."""
    paper = setup_paper_with_snapshot["paper"]
    snapshot = setup_paper_with_snapshot["snapshot"]
    claim = ClaimMap(
        paper_id=paper.id,
        claim_text="Made-up claim.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref=json.dumps({"quote": "100,000 firms went bankrupt — fabricated"}),
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [claim])
    assert claim.id in failures
    assert "not found in cited snapshot" in failures[claim.id]


@pytest.mark.asyncio
async def test_no_quote_field_passes_quietly(db_session, setup_paper_with_snapshot):
    """A claim with a span ref but no `quote` field is not mechanically
    checked beyond bytes-retrievability — the LLM still inspects it."""
    paper = setup_paper_with_snapshot["paper"]
    snapshot = setup_paper_with_snapshot["snapshot"]
    claim = ClaimMap(
        paper_id=paper.id,
        claim_text="Claim referencing a paragraph with no exact quote.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref=json.dumps({"page": 3, "paragraph": 2}),
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [claim])
    assert failures == {}


@pytest.mark.asyncio
async def test_malformed_span_ref_fails(db_session, setup_paper_with_snapshot):
    """Garbage source_span_ref → mechanical failure (don't silently accept)."""
    paper = setup_paper_with_snapshot["paper"]
    snapshot = setup_paper_with_snapshot["snapshot"]
    claim = ClaimMap(
        paper_id=paper.id,
        claim_text="Claim with broken JSON span ref.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref="{not valid",
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [claim])
    assert claim.id in failures
    assert "not valid JSON" in failures[claim.id]


@pytest.mark.asyncio
async def test_unretrievable_bytes_fails(db_session, setup_paper_with_snapshot, monkeypatch):
    """If the snapshot's bytes are not in the store, the claim fails."""
    paper = setup_paper_with_snapshot["paper"]
    # Create a snapshot whose hash points at NOTHING in the store.
    bogus_snapshot = SourceSnapshot(
        source_card_id=setup_paper_with_snapshot["source_card"].id,
        snapshot_hash="f" * 64,  # hash of nothing
        snapshot_path="/tmp/does_not_exist",
        file_size_bytes=0,
        record_count=0,
        fetched_at=datetime.now(UTC),
        provenance_proof_json=json.dumps({"method": "http"}),
    )
    db_session.add(bogus_snapshot)
    await db_session.flush()

    claim = ClaimMap(
        paper_id=paper.id,
        claim_text="Claim citing a snapshot whose bytes vanished.",
        claim_type="empirical",
        source_card_id=bogus_snapshot.source_card_id,
        source_snapshot_id=bogus_snapshot.id,
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [claim])
    assert claim.id in failures
    assert "unretrievable" in failures[claim.id]


# ── _apply_mechanical_failures ────────────────────────────────────────────────


def test_apply_mechanical_failures_overrides_llm_pass():
    """An LLM that says ``overall=pass`` is overridden to ``fail`` when the
    claim has a mechanical failure."""
    claim = ClaimMap(
        id=42,
        paper_id="p",
        claim_text="A faithfully reproduced quote.",
        claim_type="empirical",
        verification_status="pending",
    )

    llm_verification = {
        "claim_verifications": [
            {
                "claim_text": "A faithfully reproduced quote.",
                "evidence_link": {"status": "verified", "note": "looks fine"},
                "citation_accuracy": {"status": "verified", "note": "ok"},
                "causal_language": {"status": "not_applicable", "note": ""},
                "tier_compliance": {"status": "compliant", "note": ""},
                "scope_accuracy": {"status": "within_bounds", "note": ""},
                "overall": "pass",
            }
        ],
        "summary": {
            "total_claims": 1,
            "passed": 1,
            "failed": 0,
            "warnings": 0,
            "critical_violations": [],
            "recommendation": "approve",
        },
    }

    result = _apply_mechanical_failures(
        llm_verification,
        [claim],
        {42: "Quote 'foo' not found in snapshot"},
    )

    assert result["claim_verifications"][0]["overall"] == "fail"
    assert result["claim_verifications"][0]["evidence_link"]["status"] == "missing"
    assert result["summary"]["passed"] == 0
    assert result["summary"]["failed"] == 1
    assert result["summary"]["recommendation"] == "reject"
    assert any("Mechanical verification" in v for v in result["summary"]["critical_violations"])


def test_apply_mechanical_failures_appends_missing_entry():
    """If the LLM didn't return an entry for the failing claim at all, we
    still record a fail entry rather than silently dropping the failure."""
    claim = ClaimMap(
        id=7,
        paper_id="p",
        claim_text="An entirely unanswered claim.",
        claim_type="empirical",
        verification_status="pending",
    )

    llm_verification = {
        "claim_verifications": [],  # LLM said nothing about this claim
        "summary": {
            "total_claims": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "critical_violations": [],
            "recommendation": "approve",
        },
    }

    result = _apply_mechanical_failures(
        llm_verification,
        [claim],
        {7: "Snapshot bytes unretrievable"},
    )

    assert len(result["claim_verifications"]) == 1
    assert result["claim_verifications"][0]["claim_text"] == "An entirely unanswered claim."
    assert result["claim_verifications"][0]["overall"] == "fail"
    assert result["summary"]["failed"] == 1
    assert result["summary"]["recommendation"] == "reject"


def test_apply_mechanical_failures_noop_when_empty():
    """No mechanical failures → verification dict passes through unchanged."""
    llm_verification = {
        "claim_verifications": [{"claim_text": "x", "overall": "pass"}],
        "summary": {"recommendation": "approve"},
    }
    result = _apply_mechanical_failures(llm_verification, [], {})
    assert result is llm_verification
