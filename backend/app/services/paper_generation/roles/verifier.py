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
    paper_id: str,
    result_manifest: dict[str, Any] | None = None,
    provider: LLMProvider | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Full verification of a manuscript.

    Internally manages DB sessions in three phases (read → LLM → write)
    so we never hold a connection across the LLM call.

    The ``session`` parameter is kept for back-compat but ignored.
    """
    del session  # explicitly ignored

    # ── Phase 1: reads (short-lived session) ─────────────────────────
    async with async_session() as s:
        await _load_paper(s, paper_id)  # validates paper exists
        lock = await _load_active_lock(s, paper_id)
        if lock is None:
            raise ValueError(
                f"No active lock for paper '{paper_id}'. "
                "Cannot verify without a locked design."
            )

        stmt = select(ClaimMap).where(ClaimMap.paper_id == paper_id)
        result = await s.execute(stmt)
        claims = list(result.scalars().all())

        if not claims:
            logger.warning(
                "No claims found for paper %s -- nothing to verify", paper_id
            )
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

        # Build claims YAML for the LLM (detach from session)
        claims_data = [
            {
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
        protocol_type = lock.lock_protocol_type
        inference_level = _determine_inference_level(protocol_type)

    claims_yaml = yaml.dump(claims_data, default_flow_style=False, sort_keys=False)

    # ── Phase 2: LLM call (no session held) ──────────────────────────
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        from app.config import settings

        model = settings.claude_opus_model

    prompt = VERIFY_USER_PROMPT.format(
        paper_id=paper_id,
        protocol_type=protocol_type,
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


async def _load_active_lock(
    session: AsyncSession, paper_id: str
) -> LockArtifact | None:
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
    from app.utils import utcnow_naive

    # Build a lookup by claim_text (best-effort matching)
    verify_map: dict[str, dict] = {}
    for v in verifications:
        text = v.get("claim_text", "")
        verify_map[text] = v

    # claim_map.verified_at is TIMESTAMP WITHOUT TIME ZONE on Postgres;
    # asyncpg refuses to silently strip tzinfo. Use utcnow_naive().
    now = utcnow_naive()
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
        claim.verified_at = now
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
