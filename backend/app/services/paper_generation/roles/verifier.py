"""Verifier role: cross-checks claims against source spans and result objects.

Boundary: Read-only. The Verifier flags violations and produces a report.
           It cannot fix anything -- that is the Drafter's job on revision.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.claim_map import ClaimMap
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.source_card import SourceCard
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider

logger = logging.getLogger(__name__)

# Verifier batches claims into chunks of this size. Production data
# on the LLM's response coverage at various sizes:
#
#   - 50 (apep_28011bda): truncated, 0 statuses returned
#   - 15 (apep_80c3df8f): 11/25 statuses, 14 pending  (44%)
#   - 5  (apep_8f5c16b6): 6/18 statuses, 12 pending   (33%)
#   - 1  (apep_de279513): 1/19 statuses, 18 pending   (5% — REGRESSED)
#
# Going to batch=1 (per-claim verification) was hypothesised to be
# the structural fix — eliminate cherry-picking by giving the LLM
# exactly one task per call. Empirically it made things WORSE, likely
# because (a) the prompt becomes mostly context with very little
# task, and (b) Anthropic may rate-limit aggressive sequential calls.
#
# 5 is the best partial-working state we've observed. The downstream
# L2 coverage check is updated to count both verified AND failed as
# "covered" (they were processed by Verifier), so partial-but-real
# verification doesn't punish papers as hard as it did when only
# `verified` counted.
_VERIFIER_BATCH_SIZE = 5

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
Verify the following {claim_count} claims from paper {paper_id}.

Lock protocol type: {protocol_type}
Permitted inference level: {inference_level}

Claims to verify:
{claims_yaml}

Available source cards and their tiers:
{source_tiers}

Source excerpts (the actual fetched text from each cited source —
use these to verify CITATION ACCURACY and SCOPE ACCURACY rather than
refusing to assess on grounds that you "haven't read the source"):
{source_excerpts}

Result objects from analysis:
{result_objects}

For EACH claim, check:
1. EVIDENCE LINK: Does the claim have a valid source span or result object reference?
2. CITATION ACCURACY: If citing a source, does the source actually support the claim?
   Check against the source excerpt above. If the excerpt clearly supports the
   claim → "verified". If it contradicts the claim → "fabricated". If the
   excerpt is silent on the claim's specific point → "unsupported".
3. CAUSAL LANGUAGE: Does the claim use causal language? Is that permitted by the protocol?
4. TIER COMPLIANCE: If the claim is central, is it anchored by Tier A or B (not Tier C)?
5. SCOPE ACCURACY: Does the claim stay within the bounds of what the evidence supports?
   Compare the claim's specificity against the excerpt: claims that are broader
   than the source warrants are "overstated".

CRITICAL COMPLETENESS REQUIREMENT:
- Your response's "claim_verifications" array MUST have EXACTLY {claim_count} entries.
- Output ONE entry per claim above, in the SAME ORDER as the input list.
- Each entry's "claim_id" MUST match the corresponding input claim's claim_id.
- Do NOT skip claims, summarise multiple claims into one entry, or omit any claim_id.
- If you are uncertain about a claim, still output an entry with overall="warning"
  and a note explaining the uncertainty — do not omit the claim.

Return JSON:
{{
  "claim_verifications": [
    {{
      "claim_id": int,
      "claim_text": "string (echo of the input verbatim is preferred)",
      "evidence_link": {{"status": "verified|missing|weak", "note": "string"}},
      "citation_accuracy": {{"status": "verified|fabricated|unsupported", "note": "string"}},
      "causal_language": {{"status": "appropriate|violation|not_applicable", "note": "string"}},
      "tier_compliance": {{"status": "compliant|violation|not_applicable", "note": "string"}},
      "scope_accuracy": {{"status": "within_bounds|overstated|not_applicable", "note": "string"}},
      "overall": "pass|fail|warning"
    }}
  ],
  "summary": {{
    "total_claims": {claim_count},
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
    paper_id: str,
    result_manifest: dict[str, Any] | None = None,
    provider: LLMProvider | None = None,
    session: AsyncSession | None = None,
    status_filter: str | None = None,
) -> dict[str, Any]:
    """Full verification of a manuscript.

    Internally manages DB sessions in three phases (read → LLM → write)
    so we never hold a connection across the LLM call.

    Parameters
    ----------
    status_filter:
        When given, only verify claims whose ``verification_status`` matches.
        Default ``None`` verifies every claim. Useful values:
          - ``"pending"``: re-verify claims the Verifier dropped on a prior
            pass. Combined with multiple invocations, coverage approaches
            100% incrementally — the workaround for the LLM's
            cherry-picking behavior documented in PRs #50/#52/#53/#54.
          - ``"failed"``: re-check claims that previously failed (e.g.
            after a Drafter rewrite).

    The ``session`` parameter is kept for back-compat but ignored.
    """
    del session  # explicitly ignored

    # ── Phase 1: reads (short-lived session) ─────────────────────────
    async with async_session() as s:
        await _load_paper(s, paper_id)  # validates paper exists
        lock = await _load_active_lock(s, paper_id)
        if lock is None:
            raise ValueError(
                f"No active lock for paper '{paper_id}'. Cannot verify without a locked design."
            )

        stmt = select(ClaimMap).where(ClaimMap.paper_id == paper_id)
        if status_filter is not None:
            stmt = stmt.where(ClaimMap.verification_status == status_filter)
        result = await s.execute(stmt)
        claims = list(result.scalars().all())

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

        # Build claims YAML for the LLM (detach from session).
        # IMPORTANT: include claim_id so the LLM's response can be matched
        # back to the right ClaimMap row regardless of whether the LLM
        # echoes claim_text verbatim. Production paper apep_6fc2020e had
        # 25 claims but only 5 got their verification status updated
        # because text-equality matching failed on 20 (LLM paraphrased
        # or summarised the text). Matching by integer ID is robust.
        claims_data = [
            {
                "claim_id": c.id,
                "claim_text": c.claim_text,
                "claim_type": c.claim_type,
                "source_card_id": c.source_card_id,
                "source_span_ref": c.source_span_ref,
                "result_object_ref": c.result_object_ref,
            }
            for c in claims
        ]
        # Capture claim IDs so the write-back phase can re-load them.
        claim_ids = [c.id for c in claims]

        source_tiers = await _build_source_tier_map(s)
        # Load source excerpts for every source cited by the claims
        # we're verifying. PR #65 — gives the LLM actual text to
        # check claims against rather than just source IDs.
        cited_source_ids: set[str] = {
            c.source_card_id for c in claims if c.source_card_id
        }
        source_excerpts = await _load_source_excerpts(s, cited_source_ids)
        protocol_type = lock.lock_protocol_type
        inference_level = _determine_inference_level(protocol_type)

    # ── Phase 2: LLM call(s) (no session held) ──────────────────────
    # Batch claims into chunks so the LLM prompt stays manageable.
    # Production paper apep_28011bda had 50 claims; sending all 50
    # in one prompt caused the Verifier's response to be truncated
    # and zero claim statuses got updated.
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        from app.config import settings

        model = settings.claude_opus_model

    result_objects_str = (
        json.dumps(result_manifest.get("result_objects", {}), indent=2)
        if result_manifest
        else "(no result objects available)"
    )

    aggregate_results: list[dict] = []
    aggregate_summary = {
        "total_claims": 0,
        "passed": 0,
        "failed": 0,
        "warnings": 0,
        "critical_violations": [],
        "recommendation": "approve",
    }

    # Walk claims in chunks of up to _VERIFIER_BATCH_SIZE
    for batch_start in range(0, len(claims_data), _VERIFIER_BATCH_SIZE):
        batch = claims_data[batch_start : batch_start + _VERIFIER_BATCH_SIZE]
        batch_yaml = yaml.dump(batch, default_flow_style=False, sort_keys=False)

        prompt = VERIFY_USER_PROMPT.format(
            paper_id=paper_id,
            protocol_type=protocol_type,
            inference_level=inference_level,
            claims_yaml=batch_yaml,
            source_tiers=source_tiers,
            source_excerpts=source_excerpts,
            result_objects=result_objects_str,
            claim_count=len(batch),
        )

        response = await provider.complete(
            messages=[
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.2,
            max_tokens=16384,
        )

        batch_verification = _parse_json_object(response)
        batch_results = batch_verification.get("claim_verifications", [])
        batch_summary = batch_verification.get("summary", {})

        # Completeness check: production paper apep_3cdecd97 had 14/25
        # claims stuck at "pending" because the LLM cherry-picked which
        # ones to verify. The strengthened prompt asks for exactly
        # `len(batch)` entries; warn here when the response falls short.
        if len(batch_results) < len(batch):
            missing = len(batch) - len(batch_results)
            logger.warning(
                "Verifier batch %d/%d: LLM returned %d of %d expected "
                "verifications — %d claim(s) will stay 'pending' unless "
                "matched by a later batch.",
                (batch_start // _VERIFIER_BATCH_SIZE) + 1,
                (len(claims_data) + _VERIFIER_BATCH_SIZE - 1) // _VERIFIER_BATCH_SIZE,
                len(batch_results),
                len(batch),
                missing,
            )

        aggregate_results.extend(batch_results)
        aggregate_summary["total_claims"] += batch_summary.get("total_claims", len(batch_results))
        aggregate_summary["passed"] += batch_summary.get("passed", 0)
        aggregate_summary["failed"] += batch_summary.get("failed", 0)
        aggregate_summary["warnings"] += batch_summary.get("warnings", 0)
        aggregate_summary["critical_violations"].extend(
            batch_summary.get("critical_violations", [])
        )
        # Worst recommendation across batches wins.
        rec_priority = {"reject": 0, "revise": 1, "approve": 2}
        if rec_priority.get(batch_summary.get("recommendation", "approve"), 99) < rec_priority.get(
            aggregate_summary["recommendation"], 99
        ):
            aggregate_summary["recommendation"] = batch_summary["recommendation"]

        logger.info(
            "Verifier batch %d/%d: %d claims, passed=%d failed=%d",
            (batch_start // _VERIFIER_BATCH_SIZE) + 1,
            (len(claims_data) + _VERIFIER_BATCH_SIZE - 1) // _VERIFIER_BATCH_SIZE,
            len(batch),
            batch_summary.get("passed", 0),
            batch_summary.get("failed", 0),
        )

    verification = {
        "claim_verifications": aggregate_results,
        "summary": aggregate_summary,
    }

    # ── Phase 3: writes (short-lived session) ────────────────────────
    claim_results = verification.get("claim_verifications", [])
    summary = verification.get("summary", {})
    recommendation = summary.get("recommendation", "revise")

    async with async_session() as s:
        # Re-load claims by ID so they're attached to this fresh session.
        reload_stmt = select(ClaimMap).where(ClaimMap.id.in_(claim_ids))
        reloaded = (await s.execute(reload_stmt)).scalars().all()
        await _update_claim_statuses(s, paper_id, reloaded, claim_results)

        paper = await _load_paper(s, paper_id)
        paper.funnel_stage = "reviewing"
        s.add(paper)
        await s.commit()

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


async def _load_source_excerpts(
    session: AsyncSession,
    source_ids: set[str],
    max_chars_per_source: int = 2000,
) -> str:
    """Load fetched source content as formatted excerpts for the LLM.

    For each source_card_id used by the batch's claims, find the most
    recent SourceSnapshot and read up to ``max_chars_per_source`` chars
    from its on-disk file. Returns a formatted string suitable for
    insertion into the Verifier prompt.

    Best-effort: if the snapshot file is missing (Render's ephemeral
    filesystem may have wiped it on a redeploy), skip that source with
    a placeholder note rather than failing the whole verification.

    Production paper apep_b4680e6e (autonomous-loop run 25212981303)
    motivated this: 23 of 25 doctrinal claims stayed at status='pending'
    because the Verifier had only source IDs (e.g. "courtlistener")
    and tier metadata to work with — no actual case text. The LLM
    couldn't assess "Court X held Y" without reading the underlying
    decision, so it returned no determinations rather than fabricating
    verifications.
    """
    from pathlib import Path

    from app.models.source_snapshot import SourceSnapshot

    if not source_ids:
        return "(no sources cited by claims in this batch)"

    # For each source_id, find the most recent snapshot.
    snapshots_stmt = (
        select(SourceSnapshot)
        .where(SourceSnapshot.source_card_id.in_(source_ids))
        .order_by(SourceSnapshot.fetched_at.desc())
    )
    snapshots = (await session.execute(snapshots_stmt)).scalars().all()

    # Group by source, keep the most recent.
    latest_by_source: dict[str, SourceSnapshot] = {}
    for snap in snapshots:
        if snap.source_card_id not in latest_by_source:
            latest_by_source[snap.source_card_id] = snap

    if not latest_by_source:
        return (
            "(no source snapshots available for the cited sources — "
            "verify based on claim/source-card metadata only)"
        )

    excerpt_blocks: list[str] = []
    for source_id, snap in sorted(latest_by_source.items()):
        path = Path(snap.snapshot_path)
        if not path.is_file():
            excerpt_blocks.append(
                f"--- {source_id} ---\n"
                f"(snapshot file missing on disk — likely wiped by a "
                f"Render redeploy; verify on metadata only)"
            )
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            excerpt_blocks.append(
                f"--- {source_id} ---\n(read error: {e})"
            )
            continue

        excerpt = content[:max_chars_per_source]
        truncation_note = (
            f"\n[...truncated; full snapshot is {len(content)} chars]"
            if len(content) > max_chars_per_source
            else ""
        )
        excerpt_blocks.append(
            f"--- {source_id} ---\n{excerpt}{truncation_note}"
        )

    return "\n\n".join(excerpt_blocks)


async def _update_claim_statuses(
    session: AsyncSession,
    paper_id: str,
    claims: list[ClaimMap],
    verifications: list[dict[str, Any]],
) -> None:
    """Update ClaimMap verification statuses based on verifier output.

    Matching strategy (in priority order):
      1. By integer ``claim_id`` — robust regardless of text fidelity.
         The verifier prompt now sends claim_id with each claim and
         asks the LLM to echo it back.
      2. By exact ``claim_text`` equality — fallback for older runs or
         LLM responses that omitted claim_id.

    Production paper apep_6fc2020e had 25 claims but only 5 got their
    status updated because text matching failed on 20 (the LLM
    paraphrased the text). With ID matching most claims should resolve
    cleanly; the remaining "pending" rows then represent real LLM
    omissions worth investigating.
    """
    from app.utils import utcnow_naive

    # Build dual lookups: by id (preferred), then by text (fallback).
    by_id: dict[int, dict] = {}
    by_text: dict[str, dict] = {}
    for v in verifications:
        cid = v.get("claim_id")
        if isinstance(cid, int):
            by_id[cid] = v
        text = v.get("claim_text", "")
        if text:
            by_text[text] = v

    # claim_map.verified_at is TIMESTAMP WITHOUT TIME ZONE on Postgres;
    # asyncpg refuses to silently strip tzinfo. Use utcnow_naive().
    now = utcnow_naive()
    matched_id = 0
    matched_text = 0
    unmatched = 0
    for claim in claims:
        v = by_id.get(claim.id)
        if v is not None:
            matched_id += 1
        else:
            v = by_text.get(claim.claim_text)
            if v is not None:
                matched_text += 1
        if v is None:
            unmatched += 1
            continue

        overall = v.get("overall", "warning")
        if overall == "pass":
            claim.verification_status = "verified"
        elif overall == "fail":
            claim.verification_status = "failed"
        else:
            claim.verification_status = "pending"

        claim.verified_by = "verifier_role"
        claim.verified_at = now
        session.add(claim)

    if unmatched:
        logger.warning(
            "Verifier: paper %s had %d unmatched claim(s) (%d by id, "
            "%d by text). Unmatched claims keep verification_status='pending'.",
            paper_id,
            unmatched,
            matched_id,
            matched_text,
        )
    else:
        logger.info(
            "Verifier: paper %s all %d claims matched (%d by id, %d by text)",
            paper_id,
            len(claims),
            matched_id,
            matched_text,
        )

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
