"""Designer role: writes lock artifacts (frozen research designs).

Boundary: Outputs a lock artifact containing the full research design.
           Once a lock is created, no downstream role (including Designer
           itself) can modify the immutable fields.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider
from app.services.storage.lock_manager import (
    LOCK_IMMUTABLE_FIELDS,
    LOCK_MUTABLE_FIELDS,
    create_lock,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

DESIGN_SYSTEM_PROMPT = """\
You are the Designer, responsible for producing a complete, frozen research \
design that will govern all downstream work on this paper. The design must be \
precise enough that a different team could execute it without ambiguity.

HARD BOUNDARIES:
- You receive an idea card and family metadata as input.
- You output a YAML research design and a narrative memo.
- After the lock is created, you CANNOT modify any immutable field.
"""

DESIGN_USER_PROMPT = """\
Create a research design YAML for the following idea card.

Paper ID: {paper_id}
Family: {family_name} ({family_id})
Lock protocol type: {lock_protocol_type}

Idea card:
{idea_yaml}

REQUIRED IMMUTABLE FIELDS for protocol "{lock_protocol_type}":
{immutable_fields}

ALLOWED MUTABLE FIELDS (can evolve later):
{mutable_fields}

Generate a YAML document that specifies ALL immutable fields with precise, \
unambiguous definitions. Also fill in any mutable fields with initial values.

Additionally, write a narrative_memo (2-3 paragraphs) explaining:
1. Why this design is appropriate for the research question
2. Key assumptions and their justification
3. What would need to change if a kill condition is triggered

Return JSON with two keys:
{{
  "design_yaml": "<the full YAML string>",
  "narrative_memo": "<the narrative memo>"
}}

No markdown, no commentary outside the JSON."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_research_design(
    session: AsyncSession,
    paper_id: str,
    idea_card: dict[str, Any],
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Create a research design YAML from an idea card.

    Uses the family's lock_protocol_type to determine required fields.
    Generates all fields specified by LOCK_IMMUTABLE_FIELDS for the protocol.
    Returns the YAML content and narrative memo.
    """
    paper = await _load_paper(session, paper_id)
    if paper.family_id is None:
        raise ValueError(f"Paper '{paper_id}' has no family_id assigned.")

    family = await _load_family(session, paper.family_id)
    protocol_type = family.lock_protocol_type

    immutable = LOCK_IMMUTABLE_FIELDS.get(protocol_type)
    if immutable is None:
        raise ValueError(
            f"Unknown lock protocol type '{protocol_type}'. "
            f"Known: {list(LOCK_IMMUTABLE_FIELDS.keys())}"
        )
    mutable = LOCK_MUTABLE_FIELDS.get(protocol_type, [])

    idea_yaml = yaml.dump(idea_card, default_flow_style=False, sort_keys=False)

    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = settings.claude_opus_model

    prompt = DESIGN_USER_PROMPT.format(
        paper_id=paper_id,
        family_name=family.name,
        family_id=family.id,
        lock_protocol_type=protocol_type,
        idea_yaml=idea_yaml,
        immutable_fields="\n".join(f"  - {f}" for f in immutable),
        mutable_fields="\n".join(f"  - {f}" for f in mutable) if mutable else "  (none)",
    )

    response = await provider.complete(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.4,
        max_tokens=8192,
    )

    parsed = _parse_json_object(response)
    design_yaml = parsed.get("design_yaml", "")
    narrative_memo = parsed.get("narrative_memo", "")

    # Validate that all immutable fields are present in the YAML
    _validate_immutable_fields(design_yaml, immutable, protocol_type)

    logger.info(
        "Designer created research design for paper %s (protocol=%s)",
        paper_id,
        protocol_type,
    )

    return {
        "design_yaml": design_yaml,
        "narrative_memo": narrative_memo,
        "protocol_type": protocol_type,
        "immutable_fields": immutable,
        "mutable_fields": mutable,
    }


async def lock_design(
    session: AsyncSession,
    paper_id: str,
    design_yaml: str,
    narrative_memo: str,
    locked_by: str = "system",
) -> LockArtifact:
    """Lock the research design by delegating to lock_manager.create_lock().

    After this call, no downstream role can modify immutable fields.
    Updates Paper.funnel_stage to 'locked'.
    """
    lock_artifact = await create_lock(
        session=session,
        paper_id=paper_id,
        lock_yaml_content=design_yaml,
        locked_by=locked_by,
        narrative_memo=narrative_memo,
    )

    # Update funnel stage
    paper = await _load_paper(session, paper_id)
    paper.funnel_stage = "locked"
    session.add(paper)
    await session.flush()

    logger.info(
        "Designer locked design for paper %s (version=%d, hash=%s)",
        paper_id,
        lock_artifact.version,
        lock_artifact.lock_hash[:16],
    )
    return lock_artifact


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


async def _load_family(session: AsyncSession, family_id: str) -> PaperFamily:
    stmt = select(PaperFamily).where(PaperFamily.id == family_id)
    result = await session.execute(stmt)
    family = result.scalar_one_or_none()
    if family is None:
        raise ValueError(f"Paper family '{family_id}' not found.")
    return family


def _parse_json_object(response: str) -> dict:
    """Extract a JSON object from an LLM response string."""
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse design JSON from LLM response")
        return {"design_yaml": "", "narrative_memo": ""}


def _validate_immutable_fields(
    design_yaml: str, immutable_fields: list[str], protocol_type: str
) -> None:
    """Warn if any immutable fields are missing from the design YAML."""
    try:
        parsed = yaml.safe_load(design_yaml) or {}
    except yaml.YAMLError:
        logger.warning("Could not parse design YAML for validation")
        return

    missing = [f for f in immutable_fields if f not in parsed]
    if missing:
        logger.warning(
            "Design YAML for protocol '%s' is missing immutable fields: %s",
            protocol_type,
            missing,
        )
