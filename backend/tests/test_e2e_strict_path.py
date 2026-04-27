"""Step 4: end-to-end integration test for the new "real data, real claims" path.

This is the first test that exercises Steps 1-3 together — DATA_MODE=real,
provenance-proof persistence, L2 enforcement, and mechanical claim
verification — against a realistic paper-with-snapshot fixture.

Three scenarios:

1. **Happy path.** A real source returns bytes; the snapshot is created with
   an HTTP proof; a claim cites a quote that actually appears in the bytes.
   Every new gate accepts the paper.

2. **Permissive-mode placeholder.** DATA_MODE=permissive (dev-only fallback)
   produces a placeholder snapshot. L2 Provenance correctly rejects the
   resulting claim because the snapshot's proof method is "placeholder", not
   "http"/"vcr".

3. **Real data + fabricated claim.** The snapshot is real (passes L2), but
   the claim's quote does NOT appear in the snapshot bytes. The Verifier's
   mechanical check catches the fabrication and produces a failure that
   overrides any LLM judgement.

HTTP traffic is mocked at the data-source registry level — the same
``make_http_proof()`` code path runs against synthetic-but-realistic
response bytes, so the test exercises the production proof shape end-to-end
without hitting external APIs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_map import ClaimMap
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.source_card import SourceCard
from app.services.data_sources.base import FetchResult, make_http_proof
from app.services.paper_generation.data_fetcher import DataFetchError
from app.services.paper_generation.roles.data_steward import fetch_and_snapshot
from app.services.paper_generation.roles.verifier import _mechanical_verify_claims
from app.services.review_pipeline.l2_provenance import _check_provenance_proofs

# ── Realistic source content used across happy-path tests ─────────────────────

SNAPSHOT_TEXT = (
    "OpenAlex Records Export\n"
    "id,title,publication_year,cited_by_count,top_concept\n"
    "W123,Algorithmic Fairness in Government Procurement,2023,42,AI governance\n"
    "W456,Audit Mechanisms for Automated Decisions,2022,17,AI governance\n"
    "W789,Disparate Impact in Public-Sector ML,2024,8,AI governance\n"
)
SNAPSHOT_BYTES = SNAPSHOT_TEXT.encode("utf-8")


# ── Fixture: full paper graph (paper + family + lock + source_card) ──────────


@pytest_asyncio.fixture
async def paper_graph(db_session: AsyncSession, monkeypatch, tmp_path):
    """Stand up a Paper + PaperFamily + LockArtifact + SourceCard and point
    the artifact store at a clean tmp dir. Tests then call fetch_and_snapshot
    and add ClaimMaps as appropriate.
    """
    monkeypatch.setattr("app.config.settings.artifact_store_path", str(tmp_path))

    family = PaperFamily(
        id="F_E2E",
        name="E2E Strict Path",
        short_name="E2E",
        description="for end-to-end tests of the new strict path",
        lock_protocol_type="empirical_causal",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    paper = Paper(
        id="paper_e2e_1",
        title="A Paper Built On Real Data",
        family_id="F_E2E",
        source="ape",
        status="draft",
        funnel_stage="locked",
    )
    db_session.add(paper)

    source_card = SourceCard(
        id="openalex",
        name="OpenAlex",
        url="https://api.openalex.org/works",
        tier="A",
        source_type="api",
        access_method="api",
        legal_basis="public domain (CC0)",
        claim_permissions=json.dumps(["bibliometric", "citation_counts"]),
        claim_prohibitions=json.dumps(["causal_inference"]),
        content_hash="0" * 64,
    )
    db_session.add(source_card)
    await db_session.flush()

    lock = LockArtifact(
        paper_id=paper.id,
        family_id=family.id,
        lock_protocol_type="empirical_causal",
        lock_hash="lockhash" + "0" * 56,
        lock_yaml="design: test",
        immutable_fields=json.dumps(["research_question", "method"]),
        is_active=True,
    )
    db_session.add(lock)
    await db_session.commit()

    return {
        "paper": paper,
        "family": family,
        "source_card": source_card,
        "lock": lock,
    }


def _make_successful_fetch_result(file_path: Path) -> FetchResult:
    """Write SNAPSHOT_BYTES to disk and return a FetchResult with HTTP proof.

    Mirrors what an OpenAlex (or any) source client does on a real fetch.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(SNAPSHOT_BYTES)
    return FetchResult(
        success=True,
        file_path=str(file_path),
        row_count=3,
        columns=["id", "title", "publication_year", "cited_by_count", "top_concept"],
        description="Fetched 3 rows from OpenAlex",
        proof=make_http_proof(
            request_url="https://api.openalex.org/works?search=ai+governance&per_page=200",
            response_status=200,
            response_body=SNAPSHOT_BYTES,
            fetched_via="openalex_client_v1",
        ),
    )


# ── Scenario 1: happy path ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_real_data_real_claims(db_session, paper_graph, monkeypatch, tmp_path):
    """Real-fetch snapshot + verifiable quote → every gate accepts."""

    # DATA_MODE=real (default already, but be explicit).
    monkeypatch.setattr("app.services.paper_generation.data_fetcher.settings.data_mode", "real")
    monkeypatch.setattr(
        "app.services.paper_generation.roles.data_steward.settings.data_mode", "real"
    )

    # Mock the registry: when data_steward calls fetch_from_source, hand back
    # a successful FetchResult whose `proof` was built by make_http_proof.
    async def fake_fetch_from_source(source_id, params, output_dir, api_key=None):
        assert source_id == "openalex"
        return _make_successful_fetch_result(Path(output_dir) / "openalex.csv")

    monkeypatch.setattr(
        "app.services.data_sources.registry.fetch_from_source",
        fake_fetch_from_source,
    )

    # ── Step 1+2: fetch + snapshot ───────────────────────────────────────
    snapshot = await fetch_and_snapshot(
        db_session,
        paper_id=paper_graph["paper"].id,
        source_id="openalex",
        fetch_params={"query_parameters": {"search_term": "ai governance"}},
    )
    await db_session.commit()

    # The snapshot must carry an HTTP proof.
    assert snapshot.provenance_proof_json is not None
    proof = json.loads(snapshot.provenance_proof_json)
    assert proof["method"] == "http"
    assert proof["response_status"] == 200
    assert proof["fetched_via"] == "openalex_client_v1"

    # ── Step 2: L2 provenance check accepts the snapshot ─────────────────
    claim = ClaimMap(
        paper_id=paper_graph["paper"].id,
        claim_text="Three works on AI governance were retrieved from OpenAlex.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref=json.dumps({"quote": "Algorithmic Fairness in Government Procurement"}),
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    l2_issues = await _check_provenance_proofs(db_session, paper_graph["paper"].id)
    assert l2_issues == [], (
        f"L2 must accept a snapshot with HTTP proof, but produced issues: {l2_issues}"
    )

    # ── Step 3: mechanical verifier accepts the claim ────────────────────
    failures = await _mechanical_verify_claims(db_session, [claim])
    assert failures == {}, (
        f"Mechanical verifier must accept a claim whose quote is in the "
        f"snapshot, but produced failures: {failures}"
    )


# ── Scenario 2: permissive-mode placeholder is blocked at L2 ──────────────────


@pytest.mark.asyncio
async def test_permissive_placeholder_blocked_at_l2(db_session, paper_graph, monkeypatch, tmp_path):
    """DATA_MODE=permissive emits a placeholder snapshot — L2 rejects it
    because proof.method == "placeholder", not "http"/"vcr".
    """
    monkeypatch.setattr(
        "app.services.paper_generation.data_fetcher.settings.data_mode", "permissive"
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.data_steward.settings.data_mode",
        "permissive",
    )

    # Registry returns failure → data_steward falls back to placeholder.
    async def failing_fetch(source_id, params, output_dir, api_key=None):
        return FetchResult(success=False, error="API unavailable in test")

    monkeypatch.setattr(
        "app.services.data_sources.registry.fetch_from_source",
        failing_fetch,
    )

    snapshot = await fetch_and_snapshot(
        db_session,
        paper_id=paper_graph["paper"].id,
        source_id="openalex",
    )
    await db_session.commit()

    proof = json.loads(snapshot.provenance_proof_json)
    assert proof["method"] == "placeholder"

    claim = ClaimMap(
        paper_id=paper_graph["paper"].id,
        claim_text="A claim that should not pass review.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    l2_issues = await _check_provenance_proofs(db_session, paper_graph["paper"].id)
    assert len(l2_issues) == 1, l2_issues
    assert l2_issues[0]["severity"] == "critical"
    assert l2_issues[0]["check"] == "provenance_proof_synthetic"
    assert l2_issues[0]["proof_method"] == "placeholder"


# ── Scenario 2b: real mode hard-fails when no source returns data ─────────────


@pytest.mark.asyncio
async def test_real_mode_hard_fails_with_no_real_source(db_session, paper_graph, monkeypatch):
    """DATA_MODE=real + every source fails → DataFetchError, no snapshot
    produced. The pipeline dies before a placeholder paper can be assembled.
    """
    monkeypatch.setattr("app.services.paper_generation.data_fetcher.settings.data_mode", "real")
    monkeypatch.setattr(
        "app.services.paper_generation.roles.data_steward.settings.data_mode", "real"
    )

    async def failing_fetch(source_id, params, output_dir, api_key=None):
        return FetchResult(success=False, error="API unreachable")

    monkeypatch.setattr(
        "app.services.data_sources.registry.fetch_from_source",
        failing_fetch,
    )

    with pytest.raises(DataFetchError) as excinfo:
        await fetch_and_snapshot(
            db_session,
            paper_id=paper_graph["paper"].id,
            source_id="openalex",
        )
    assert "DATA_MODE=real" in str(excinfo.value)


# ── Scenario 3: real data, fabricated claim, blocked at the verifier ─────────


@pytest.mark.asyncio
async def test_real_data_fabricated_quote_blocked_at_verifier(
    db_session, paper_graph, monkeypatch, tmp_path
):
    """Snapshot is real (passes L2), but the claim's quote is not in the
    snapshot bytes. The mechanical verifier catches it — even though L2 is
    happy with the proof.
    """
    monkeypatch.setattr("app.services.paper_generation.data_fetcher.settings.data_mode", "real")
    monkeypatch.setattr(
        "app.services.paper_generation.roles.data_steward.settings.data_mode", "real"
    )

    async def fake_fetch_from_source(source_id, params, output_dir, api_key=None):
        return _make_successful_fetch_result(Path(output_dir) / "openalex.csv")

    monkeypatch.setattr(
        "app.services.data_sources.registry.fetch_from_source",
        fake_fetch_from_source,
    )

    snapshot = await fetch_and_snapshot(
        db_session,
        paper_id=paper_graph["paper"].id,
        source_id="openalex",
    )
    await db_session.commit()

    # Fabricated quote: this string is NOT in SNAPSHOT_TEXT.
    fabricated = ClaimMap(
        paper_id=paper_graph["paper"].id,
        claim_text="A fabricated claim with a quote that doesn't exist in the source.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref=json.dumps(
            {"quote": "10,000 firms went bankrupt due to AI procurement rules"}
        ),
        verification_status="pending",
    )
    db_session.add(fabricated)
    await db_session.commit()

    # L2 is satisfied — the proof is fine.
    l2_issues = await _check_provenance_proofs(db_session, paper_graph["paper"].id)
    assert l2_issues == [], "L2 should not flag a real-fetch snapshot"

    # But the mechanical verifier catches the fabrication.
    failures = await _mechanical_verify_claims(db_session, [fabricated])
    assert fabricated.id in failures
    assert "not found in cited snapshot" in failures[fabricated.id]


# ── Scenario 4: integrated bar — both real-fetch snapshot AND a fabricated ──
# claim are present; the paper fails because at least one claim fails the
# mechanical check, even though others would pass.


@pytest.mark.asyncio
async def test_mixed_claims_paper_fails_when_any_claim_fabricated(
    db_session, paper_graph, monkeypatch, tmp_path
):
    """A paper with multiple claims passes only if ALL claims pass mechanical
    verification. One fabricated quote alongside two valid ones → failure
    map contains the fabricated claim's ID and only that one.
    """
    monkeypatch.setattr("app.services.paper_generation.data_fetcher.settings.data_mode", "real")
    monkeypatch.setattr(
        "app.services.paper_generation.roles.data_steward.settings.data_mode", "real"
    )

    async def fake_fetch_from_source(source_id, params, output_dir, api_key=None):
        return _make_successful_fetch_result(Path(output_dir) / "openalex.csv")

    monkeypatch.setattr(
        "app.services.data_sources.registry.fetch_from_source",
        fake_fetch_from_source,
    )

    snapshot = await fetch_and_snapshot(
        db_session,
        paper_id=paper_graph["paper"].id,
        source_id="openalex",
    )
    await db_session.commit()

    valid_a = ClaimMap(
        paper_id=paper_graph["paper"].id,
        claim_text="One valid claim.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref=json.dumps({"quote": "Audit Mechanisms for Automated Decisions"}),
        verification_status="pending",
    )
    fabricated = ClaimMap(
        paper_id=paper_graph["paper"].id,
        claim_text="An impostor claim.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref=json.dumps({"quote": "this string is nowhere in the source"}),
        verification_status="pending",
    )
    valid_b = ClaimMap(
        paper_id=paper_graph["paper"].id,
        claim_text="Another valid claim.",
        claim_type="empirical",
        source_card_id=snapshot.source_card_id,
        source_snapshot_id=snapshot.id,
        source_span_ref=json.dumps({"quote": "Disparate Impact in Public-Sector ML"}),
        verification_status="pending",
    )
    db_session.add_all([valid_a, fabricated, valid_b])
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [valid_a, fabricated, valid_b])
    # Only the fabricated claim should fail.
    assert set(failures.keys()) == {fabricated.id}


# ── Sanity: snapshot proof carries the response body's SHA-256 ───────────────


@pytest.mark.asyncio
async def test_proof_response_hash_matches_real_body_bytes(
    db_session, paper_graph, monkeypatch, tmp_path
):
    """The persisted proof hashes the actual response body the source client
    saw — this is what lets future audits detect upstream API drift.
    """
    import hashlib

    monkeypatch.setattr("app.services.paper_generation.data_fetcher.settings.data_mode", "real")
    monkeypatch.setattr(
        "app.services.paper_generation.roles.data_steward.settings.data_mode", "real"
    )

    async def fake_fetch_from_source(source_id, params, output_dir, api_key=None):
        return _make_successful_fetch_result(Path(output_dir) / "openalex.csv")

    monkeypatch.setattr(
        "app.services.data_sources.registry.fetch_from_source",
        fake_fetch_from_source,
    )

    snapshot = await fetch_and_snapshot(
        db_session,
        paper_id=paper_graph["paper"].id,
        source_id="openalex",
    )

    proof = json.loads(snapshot.provenance_proof_json)
    expected_hash = hashlib.sha256(SNAPSHOT_BYTES).hexdigest()
    assert proof["response_hash"] == expected_hash
    # Also documented in the proof: when it was fetched.
    assert proof["fetched_at"].endswith("+00:00")
    # Proof timestamp roughly recent.
    fetched_at = datetime.fromisoformat(proof["fetched_at"])
    assert (datetime.now(UTC) - fetched_at).total_seconds() < 60
