"""Drafter role: composes manuscript from verified results and source spans.

Boundary: Every claim must map to a verified source span or result object.
           Cannot fabricate citations or elevate descriptive findings to causal
           claims unless the lock artifact permits that inference.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_map import ClaimMap
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

DRAFT_SYSTEM_PROMPT = """\
You are the Drafter, responsible for composing a complete academic manuscript \
from verified results and source evidence. You write in LaTeX.

HARD BOUNDARIES:
- Every empirical claim MUST reference a specific result object or source span.
- You CANNOT fabricate citations to papers that do not exist.
- You CANNOT elevate descriptive findings to causal claims UNLESS the lock \
  artifact's identification strategy explicitly permits causal inference.
- You MUST follow the venue style indicated by the family's venue_ladder.
- All tables and figures must reference verified result objects.
"""

DRAFT_USER_PROMPT = """\
Compose a complete LaTeX manuscript for paper {paper_id}.

Locked research design:
{lock_yaml}

Protocol type: {protocol_type}
Permitted inference level: {inference_level}

Result manifest (analysis outputs):
{result_manifest}

Source manifest (data sources used):
{source_manifest}

Target venue style: {venue_style}

Family description: {family_description}

Write the COMPLETE manuscript with these sections:
1. Introduction (research question, contribution, roadmap)
2. Literature Review (position paper relative to existing work)
3. Methodology (identification strategy from the lock artifact)
4. Data (describe sources with Tier classification)
5. Results (present findings referencing specific result objects)
6. Discussion (interpret findings within lock artifact constraints)
7. Conclusion (policy implications, limitations)

For EACH central claim, include a comment indicating the evidence source:
  %% CLAIM: <claim_text> | SOURCE: <source_card_id or result_object_name>

Return JSON:
{{
  "manuscript_latex": "<the full LaTeX document>",
  "claims": [
    {{
      "claim_text": "string",
      "claim_type": "empirical|descriptive|doctrinal|theoretical|historical",
      "source_type": "result_object|source_span",
      "source_ref": "string (result object name or source card ID)",
      "section": "string (which section contains this claim)"
    }}
  ],
  "bibliography_entries": [
    {{
      "key": "string (bibtex key)",
      "type": "article|book|report|dataset",
      "title": "string",
      "authors": "string",
      "year": "string",
      "source": "string (journal/publisher)"
    }}
  ]
}}

No markdown wrapper, no commentary outside the JSON."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def compose_manuscript(
    session: AsyncSession,
    paper_id: str,
    result_manifest: dict[str, Any] | None = None,
    source_manifest: dict[str, Any] | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Compose the full manuscript.

    1. Load lock artifact, result manifest, source manifest
    2. Load family's venue_ladder for style targeting
    3. Generate LaTeX sections: intro, lit review, methodology, data, results,
       discussion, conclusion
    4. For each central claim, create a ClaimMap entry linking to source/result
    5. Generate citations
    6. Return manuscript text, claim_map entries, and bibliography
    """
    paper = await _load_paper(session, paper_id)

    # Load the lock artifact
    lock = await _load_active_lock(session, paper_id)
    if lock is None:
        raise ValueError(
            f"No active lock for paper '{paper_id}'. Design must be locked before drafting."
        )

    # Load family for venue targeting
    family = await _load_family(session, paper.family_id) if paper.family_id else None

    # Determine permitted inference level from the protocol
    inference_level = _determine_inference_level(lock.lock_protocol_type)

    # Build venue style string
    venue_style = "general academic"
    if family and family.venue_ladder:
        try:
            venue_data = json.loads(family.venue_ladder)
            flagship = venue_data.get("flagship", [])
            if flagship:
                venue_style = f"targeting {flagship[0]} style"
        except (json.JSONDecodeError, TypeError):
            pass

    family_description = family.description if family else "AI governance research"

    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    prompt = DRAFT_USER_PROMPT.format(
        paper_id=paper_id,
        lock_yaml=lock.lock_yaml,
        protocol_type=lock.lock_protocol_type,
        inference_level=inference_level,
        result_manifest=json.dumps(result_manifest, indent=2)
        if result_manifest
        else "(no results yet)",
        source_manifest=json.dumps(source_manifest, indent=2)
        if source_manifest
        else "(no manifest)",
        venue_style=venue_style,
        family_description=family_description,
    )

    response = await provider.complete(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.5,
        max_tokens=32768,
    )

    parsed = _parse_json_object(response)

    manuscript_latex = parsed.get("manuscript_latex", "")
    claims_raw = parsed.get("claims", [])
    bibliography = parsed.get("bibliography_entries", [])

    # Create ClaimMap entries for each claim
    claim_map_entries: list[dict[str, Any]] = []
    for claim_data in claims_raw:
        claim_map = ClaimMap(
            paper_id=paper_id,
            claim_text=claim_data.get("claim_text", ""),
            claim_type=claim_data.get("claim_type", "descriptive"),
            source_card_id=(
                claim_data.get("source_ref")
                if claim_data.get("source_type") == "source_span"
                else None
            ),
            result_object_ref=(
                json.dumps({"name": claim_data.get("source_ref")})
                if claim_data.get("source_type") == "result_object"
                else None
            ),
            verification_status="pending",
        )
        session.add(claim_map)
        claim_map_entries.append(
            {
                "claim_text": claim_data.get("claim_text", ""),
                "claim_type": claim_data.get("claim_type", "descriptive"),
                "source_type": claim_data.get("source_type", ""),
                "source_ref": claim_data.get("source_ref", ""),
                "section": claim_data.get("section", ""),
            }
        )

    # Update funnel stage
    paper.funnel_stage = "drafting"
    session.add(paper)
    await session.flush()

    logger.info(
        "Drafter composed manuscript for paper %s (%d claims, %d bibliography entries)",
        paper_id,
        len(claim_map_entries),
        len(bibliography),
    )

    return {
        "manuscript_latex": manuscript_latex,
        "claims": claim_map_entries,
        "bibliography": bibliography,
        "inference_level": inference_level,
    }


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


async def _load_family(session: AsyncSession, family_id: str) -> PaperFamily | None:
    stmt = select(PaperFamily).where(PaperFamily.id == family_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _determine_inference_level(protocol_type: str) -> str:
    """Map protocol type to permitted inference level."""
    causal_protocols = {"empirical_causal"}
    descriptive_protocols = {"measurement_text", "synthesis_bibliometric"}
    process_protocols = {"process_tracing", "comparative_historical"}
    theory_protocols = {"theory"}
    doctrinal_protocols = {"doctrinal"}

    if protocol_type in causal_protocols:
        return "causal (with valid identification strategy)"
    elif protocol_type in descriptive_protocols:
        return "descriptive only (no causal claims)"
    elif protocol_type in process_protocols:
        return "mechanistic (within-case causal with evidence thresholds)"
    elif protocol_type in theory_protocols:
        return "theoretical (formal model implications)"
    elif protocol_type in doctrinal_protocols:
        return "interpretive (legal analysis, not causal)"
    else:
        return "descriptive only (unknown protocol, conservative default)"


def _parse_json_object(response: str) -> dict:
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse manuscript JSON from LLM response")
        return {
            "manuscript_latex": "",
            "claims": [],
            "bibliography_entries": [],
        }
