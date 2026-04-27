"""Verifier role: cross-checks claims against source spans and result objects.

Boundary: Read-only. The Verifier flags violations and produces a report.
           It cannot fix anything -- that is the Drafter's job on revision.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.claim_map import ClaimMap
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider
from app.services.storage.artifact_store import FilesystemArtifactStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

VERIFY_SYSTEM_PROMPT = """\
You are the Verifier, a strict cross-checking agent for research manuscripts. \
Your job is to examine every claim in the manuscript and verify it against the \
evidence base.

HARD BOUNDARIES:
- You are READ-ONLY. You flag problems. You do NOT fix anything.
- Every claim must trace to a source span or result object.
- Causal language is only permitted if the lock protocol allows causal inference.
- Tier C sources cannot anchor central claims.
- Citations must reference real, verifiable sources.
"""

VERIFY_USER_PROMPT = """\
Verify the following claims from paper {paper_id}.

Lock protocol type: {protocol_type}
Permitted inference level: {inference_level}

Claims to verify:
{claims_yaml}

Available source cards and their tiers:
{source_tiers}

Result objects from analysis:
{result_objects}

For EACH claim, check:
1. EVIDENCE LINK: Does the claim have a valid source span or result object reference?
2. CITATION ACCURACY: If citing a source, does the source actually support the claim?
3. CAUSAL LANGUAGE: Does the claim use causal language? Is that permitted by the protocol?
4. TIER COMPLIANCE: If the claim is central, is it anchored by Tier A or B (not Tier C)?
5. SCOPE ACCURACY: Does the claim stay within the bounds of what the evidence supports?

Return JSON:
{{
  "claim_verifications": [
    {{
      "claim_text": "string",
      "evidence_link": {{"status": "verified|missing|weak", "note": "string"}},
      "citation_accuracy": {{"status": "verified|fabricated|unsupported", "note": "string"}},
      "causal_language": {{"status": "appropriate|violation|not_applicable", "note": "string"}},
      "tier_compliance": {{"status": "compliant|violation|not_applicable", "note": "string"}},
      "scope_accuracy": {{"status": "within_bounds|overstated|not_applicable", "note": "string"}},
      "overall": "pass|fail|warning"
    }}
  ],
  "summary": {{
    "total_claims": int,
    "passed": int,
    "failed": int,
    "warnings": int,
    "critical_violations": ["string list of critical issues"],
    "recommendation": "approve|revise|reject"
  }}
}}

No markdown, no commentary outside the JSON."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def verify_manuscript(
    session: AsyncSession,
    paper_id: str,
    result_manifest: dict[str, Any] | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Full verification of a manuscript.

    1. Load all claim_map entries
    2. For each claim: verify against source span or result object
    3. Check citation accuracy (does the cited source exist and say what's claimed?)
    4. Check causal language against lock protocol permissions
    5. Check Tier C sources aren't anchoring central claims
    6. Return verification report with pass/fail per claim
    """
    paper = await _load_paper(session, paper_id)

    # Load lock artifact
    lock = await _load_active_lock(session, paper_id)
    if lock is None:
        raise ValueError(
            f"No active lock for paper '{paper_id}'. Cannot verify without a locked design."
        )

    # Load all claim map entries
    stmt = select(ClaimMap).where(ClaimMap.paper_id == paper_id)
    result = await session.execute(stmt)
    claims = result.scalars().all()

    if not claims:
        logger.warning("No claims found for paper %s -- nothing to verify", paper_id)
        return {
            "claim_verifications": [],
            "summary": {
                "total_claims": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
                "critical_violations": ["No claims found in manuscript"],
                "recommendation": "revise",
            },
        }

    # ── Step 3: mechanical claim verification ────────────────────────────
    # BEFORE the LLM is consulted, mechanically verify that claims with a
    # quoted span actually appear in the cited snapshot bytes. Mechanical
    # failures override any LLM verdict — a fabricated number doesn't get
    # to be "pass" just because the LLM finds it plausible.
    mechanical_failures = await _mechanical_verify_claims(session, claims)
    if mechanical_failures:
        logger.warning(
            "Verifier: %d/%d claim(s) fail mechanical verification for paper %s",
            len(mechanical_failures),
            len(claims),
            paper_id,
        )

    # Build claims YAML for the LLM
    claims_data = []
    for c in claims:
        claims_data.append(
            {
                "claim_text": c.claim_text,
                "claim_type": c.claim_type,
                "source_card_id": c.source_card_id,
                "source_span_ref": c.source_span_ref,
                "result_object_ref": c.result_object_ref,
            }
        )

    claims_yaml = yaml.dump(claims_data, default_flow_style=False, sort_keys=False)

    # Load source card tiers
    source_tiers = await _build_source_tier_map(session)

    # Determine inference level
    inference_level = _determine_inference_level(lock.lock_protocol_type)

    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    prompt = VERIFY_USER_PROMPT.format(
        paper_id=paper_id,
        protocol_type=lock.lock_protocol_type,
        inference_level=inference_level,
        claims_yaml=claims_yaml,
        source_tiers=source_tiers,
        result_objects=(
            json.dumps(result_manifest.get("result_objects", {}), indent=2)
            if result_manifest
            else "(no result objects available)"
        ),
    )

    response = await provider.complete(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.2,
        max_tokens=16384,
    )

    verification = _parse_json_object(response)

    # ── Step 3: merge mechanical failures into LLM verification ─────────
    # Mechanical failures hard-fail the claim, regardless of LLM verdict.
    if mechanical_failures:
        verification = _apply_mechanical_failures(verification, claims, mechanical_failures)

    # Update claim verification statuses in the database
    claim_results = verification.get("claim_verifications", [])
    await _update_claim_statuses(session, paper_id, claims, claim_results)

    # Update funnel stage
    summary = verification.get("summary", {})
    recommendation = summary.get("recommendation", "revise")

    paper.funnel_stage = "reviewing"
    session.add(paper)
    await session.flush()

    logger.info(
        "Verifier checked paper %s: %d passed, %d failed, %d warnings (rec=%s)",
        paper_id,
        summary.get("passed", 0),
        summary.get("failed", 0),
        summary.get("warnings", 0),
        recommendation,
    )

    return verification


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    paper = result.scalar_one_or_none()
    if paper is None:
        raise ValueError(f"Paper '{paper_id}' not found.")
    return paper


async def _load_active_lock(session: AsyncSession, paper_id: str) -> LockArtifact | None:
    stmt = (
        select(LockArtifact)
        .where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _build_source_tier_map(session: AsyncSession) -> str:
    """Build a text summary of source cards and their tiers."""
    stmt = select(SourceCard).where(SourceCard.active.is_(True))
    result = await session.execute(stmt)
    cards = result.scalars().all()

    if not cards:
        return "(no source cards registered)"

    lines = [f"- {sc.id}: Tier {sc.tier} ({sc.name})" for sc in cards]
    return "\n".join(lines)


async def _update_claim_statuses(
    session: AsyncSession,
    paper_id: str,
    claims: list[ClaimMap],
    verifications: list[dict[str, Any]],
) -> None:
    """Update ClaimMap verification statuses based on verifier output."""
    from datetime import datetime

    # Build a lookup by claim_text (best-effort matching)
    verify_map: dict[str, dict] = {}
    for v in verifications:
        text = v.get("claim_text", "")
        verify_map[text] = v

    for claim in claims:
        v = verify_map.get(claim.claim_text)
        if v is None:
            continue

        overall = v.get("overall", "warning")
        if overall == "pass":
            claim.verification_status = "verified"
        elif overall == "fail":
            claim.verification_status = "failed"
        else:
            claim.verification_status = "pending"

        claim.verified_by = "verifier_role"
        claim.verified_at = datetime.now(UTC)
        session.add(claim)

    await session.flush()


def _determine_inference_level(protocol_type: str) -> str:
    """Map protocol type to permitted inference level."""
    mapping = {
        "empirical_causal": "causal (with valid identification strategy)",
        "measurement_text": "descriptive only (no causal claims)",
        "synthesis_bibliometric": "descriptive only (no causal claims)",
        "process_tracing": "mechanistic (within-case causal with evidence thresholds)",
        "comparative_historical": "mechanistic (within-case causal with evidence thresholds)",
        "theory": "theoretical (formal model implications)",
        "doctrinal": "interpretive (legal analysis, not causal)",
    }
    return mapping.get(protocol_type, "descriptive only (unknown protocol)")


def _parse_json_object(response: str) -> dict:
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse verification JSON from LLM response")
        return {
            "claim_verifications": [],
            "summary": {
                "total_claims": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
                "critical_violations": ["Verification parse error"],
                "recommendation": "revise",
            },
        }


# ---------------------------------------------------------------------------
# Step 3: mechanical claim verification (source-bytes string match)
# ---------------------------------------------------------------------------


async def _mechanical_verify_claims(
    session: AsyncSession,
    claims: list[ClaimMap],
) -> dict[int, str]:
    """Verify each claim against the actual bytes of its cited snapshot.

    For every claim that references a ``source_snapshot_id``:
      1. Load the snapshot record.
      2. Retrieve the snapshot bytes from the artifact store.
      3. If the snapshot bytes can't be retrieved → mechanical failure.
      4. If the claim's ``source_span_ref`` includes a ``quote`` field, the
         quote string MUST appear (case-sensitive substring) in the snapshot
         bytes. Otherwise → mechanical failure.

    Returns a ``{claim_id: failure_reason}`` map. Claims with no
    ``source_snapshot_id`` (e.g. claims grounded purely in result objects)
    are skipped here and left to the LLM verifier; the per-paper review
    pipeline still gates them via ClaimMap.verification_status.

    Mechanical failures are hard fails: ``_apply_mechanical_failures``
    overrides the LLM verdict for these claim IDs.
    """
    failures: dict[int, str] = {}
    if not claims:
        return failures

    store = FilesystemArtifactStore(settings.artifact_store_path)
    snapshot_cache: dict[int, SourceSnapshot | None] = {}
    bytes_cache: dict[str, bytes | None] = {}

    for claim in claims:
        if not claim.source_snapshot_id:
            continue  # skip — no snapshot to verify against

        if claim.source_snapshot_id not in snapshot_cache:
            stmt = select(SourceSnapshot).where(SourceSnapshot.id == claim.source_snapshot_id)
            snapshot_cache[claim.source_snapshot_id] = (
                await session.execute(stmt)
            ).scalar_one_or_none()
        snapshot = snapshot_cache[claim.source_snapshot_id]
        if snapshot is None:
            failures[claim.id] = f"Cited snapshot {claim.source_snapshot_id} not found in database"
            continue

        if snapshot.snapshot_hash not in bytes_cache:
            bytes_cache[snapshot.snapshot_hash] = await store.retrieve(snapshot.snapshot_hash)
        body = bytes_cache[snapshot.snapshot_hash]
        if body is None:
            failures[claim.id] = (
                f"Snapshot bytes unretrievable for hash "
                f"{snapshot.snapshot_hash[:12]}... — claim cannot be mechanically "
                f"verified."
            )
            continue

        # Optional quote check: if source_span_ref carries a `quote`, it must
        # appear verbatim in the snapshot bytes.
        if claim.source_span_ref:
            try:
                span = json.loads(claim.source_span_ref)
            except (TypeError, ValueError, json.JSONDecodeError):
                failures[claim.id] = "source_span_ref is not valid JSON"
                continue

            quote = (span.get("quote") if isinstance(span, dict) else None) or ""
            quote = quote.strip()
            if quote:
                # Decode permissively — the snapshot may be UTF-8 or a CSV
                # generated locally; either way the quote should appear as
                # literal characters.
                text = body.decode("utf-8", errors="replace")
                if quote not in text:
                    excerpt = quote[:80] + ("..." if len(quote) > 80 else "")
                    failures[claim.id] = (
                        f"Quote {excerpt!r} not found in cited snapshot "
                        f"(hash={snapshot.snapshot_hash[:12]}...). The claim "
                        f"either misquotes the source or cites the wrong "
                        f"snapshot."
                    )
                    continue

    return failures


def _apply_mechanical_failures(
    verification: dict,
    claims: list[ClaimMap],
    mechanical_failures: dict[int, str],
) -> dict:
    """Override LLM verdicts for claims that failed mechanical verification.

    For each claim ID in ``mechanical_failures``:
      - Find the matching entry in ``verification["claim_verifications"]``
        (by ``claim_text``). If absent, append a synthetic entry.
      - Set ``overall = "fail"`` and ``evidence_link.status = "missing"``
        with the mechanical failure reason as the note.
      - Add the failure to ``summary.critical_violations``.
      - Recompute summary counts and force ``recommendation = "reject"``.
    """
    if not mechanical_failures:
        return verification

    claim_by_id = {c.id: c for c in claims}

    # Build a text → entry map for the LLM-produced list so we can update
    # in place, and a separate list for synthetic entries we have to add.
    claim_verifications = list(verification.get("claim_verifications", []))
    text_to_entry: dict[str, dict] = {}
    for entry in claim_verifications:
        text = entry.get("claim_text", "")
        text_to_entry[text] = entry

    for claim_id, reason in mechanical_failures.items():
        claim = claim_by_id.get(claim_id)
        if claim is None:
            continue

        entry = text_to_entry.get(claim.claim_text)
        if entry is None:
            entry = {
                "claim_text": claim.claim_text,
                "evidence_link": {"status": "missing", "note": reason},
                "citation_accuracy": {
                    "status": "unsupported",
                    "note": "Mechanical verification failed — see evidence_link.",
                },
                "causal_language": {"status": "not_applicable", "note": ""},
                "tier_compliance": {"status": "not_applicable", "note": ""},
                "scope_accuracy": {"status": "not_applicable", "note": ""},
                "overall": "fail",
            }
            claim_verifications.append(entry)
        else:
            entry["overall"] = "fail"
            entry["evidence_link"] = {
                "status": "missing",
                "note": (
                    f"Mechanical verification failed: {reason} "
                    f"(LLM said: {entry.get('evidence_link', {}).get('note', '—')})"
                ),
            }

    # Recompute summary counts.
    passed = sum(1 for v in claim_verifications if v.get("overall") == "pass")
    failed = sum(1 for v in claim_verifications if v.get("overall") == "fail")
    warnings = sum(1 for v in claim_verifications if v.get("overall") == "warning")

    summary = dict(verification.get("summary", {}))
    summary["total_claims"] = len(claim_verifications)
    summary["passed"] = passed
    summary["failed"] = failed
    summary["warnings"] = warnings

    critical = list(summary.get("critical_violations", []))
    for reason in mechanical_failures.values():
        critical.append(f"Mechanical verification: {reason}")
    summary["critical_violations"] = critical

    # Any mechanical failure forces reject — these are non-negotiable.
    summary["recommendation"] = "reject"

    return {
        "claim_verifications": claim_verifications,
        "summary": summary,
    }
