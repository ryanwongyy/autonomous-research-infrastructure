"""Scout role: proposes research ideas from governance landscape gaps.

Boundary: Read-only access to source cards and paper families.
           Cannot draft paper text or modify any existing artifacts.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper_family import PaperFamily
from app.models.source_card import SourceCard
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

IDEA_SYSTEM_PROMPT = """\
You are the Scout, an autonomous research-idea generator for the AI-governance \
research pipeline. Your sole job is to identify gaps in the governance literature \
and propose rigorous, novel research ideas.

HARD BOUNDARIES:
- You may READ source cards and family metadata. You must NOT draft paper text.
- Every idea must reference at least one publicly available data source.
- Do not propose ideas that duplicate the research questions already in the family.
"""

IDEA_USER_PROMPT = """\
Generate {count} research idea cards for paper family "{family_name}" ({family_id}).

Family description:
{family_description}

Lock protocol type: {lock_protocol_type}

Canonical research questions already explored:
{canonical_questions}

Accepted methods:
{accepted_methods}

Available public data sources (source cards):
{source_cards}

For EACH idea, return a JSON object with exactly these fields:
- research_question: one clear, testable sentence
- primary_family: "{family_id}"
- secondary_family: null or another family ID if cross-cutting
- public_data_inventory: list of source card IDs from the available sources
- expected_unit_of_analysis: string describing the unit (e.g. "country-year")
- novelty_delta: one paragraph on what is new vs existing literature
- central_inferential_risk: the main threat to validity
- kill_conditions: list of 2-4 conditions that would kill this idea

Return a JSON array of {count} idea objects. No markdown, no commentary."""

SCREEN_SYSTEM_PROMPT = """\
You are the Scout's screening module. You evaluate research idea cards on six \
dimensions using a 0-5 integer scale. Be rigorous and honest.

Scoring rubric:
- 0: Fatally flawed / not viable
- 1: Serious concerns, unlikely to succeed
- 2: Below average, significant weaknesses
- 3: Acceptable but unremarkable
- 4: Good, publishable quality
- 5: Excellent, top-tier potential

MINIMUM PASS REQUIREMENTS:
- Weighted composite >= 4.0
- Novelty >= 4
- Data adequacy >= 4
"""

SCREEN_USER_PROMPT = """\
Screen the following research idea card on six dimensions (0-5 integer scale).

Idea card:
{idea_yaml}

Score each dimension and provide a one-sentence justification:
1. importance: Does this address a meaningful governance question?
2. novelty: Is this genuinely new compared to existing literature?
3. data_adequacy: Are the proposed data sources sufficient and accessible?
4. inferential_credibility: Is the proposed method sound for the research question?
5. venue_fit: Would this fit a reputable governance/policy journal?
6. execution_burden: How feasible is execution? (5 = easy, 0 = intractable)

Weights for composite: importance=0.25, novelty=0.20, data_adequacy=0.20, \
inferential_credibility=0.20, venue_fit=0.10, execution_burden=0.05

Return a JSON object:
{{
  "scores": {{
    "importance": {{"score": int, "reason": str}},
    "novelty": {{"score": int, "reason": str}},
    "data_adequacy": {{"score": int, "reason": str}},
    "inferential_credibility": {{"score": int, "reason": str}},
    "venue_fit": {{"score": int, "reason": str}},
    "execution_burden": {{"score": int, "reason": str}}
  }},
  "weighted_composite": float,
  "pass": bool,
  "summary": str
}}

No markdown, no commentary."""

# Weights for the composite score
SCREEN_WEIGHTS = {
    "importance": 0.25,
    "novelty": 0.20,
    "data_adequacy": 0.20,
    "inferential_credibility": 0.20,
    "venue_fit": 0.10,
    "execution_burden": 0.05,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_ideas(
    session: AsyncSession,
    family_id: str,
    count: int = 10,
    provider: LLMProvider | None = None,
) -> list[dict[str, Any]]:
    """Generate idea cards for a specific paper family.

    Each idea card contains:
    - research_question: one-sentence question
    - primary_family: family ID
    - secondary_family: optional
    - public_data_inventory: list of source card IDs
    - expected_unit_of_analysis: str
    - novelty_delta: what is new vs existing literature
    - central_inferential_risk: main threat to validity
    - kill_conditions: list of conditions that would kill this idea

    Uses the family's canonical_questions and accepted_methods to guide
    generation. Queries source cards to find relevant data sources.
    """
    # Load family metadata
    family = await _load_family(session, family_id)

    canonical_questions = _parse_json_field(family.canonical_questions, [])
    accepted_methods = _parse_json_field(family.accepted_methods, [])

    # Load active source cards
    stmt = select(SourceCard).where(SourceCard.active.is_(True))
    result = await session.execute(stmt)
    source_cards = result.scalars().all()

    source_card_text = "\n".join(
        f"- {sc.id}: {sc.name} (Tier {sc.tier}, {sc.source_type}, "
        f"unit={sc.canonical_unit or 'N/A'})"
        for sc in source_cards
    )

    # Resolve provider
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    prompt = IDEA_USER_PROMPT.format(
        count=count,
        family_name=family.name,
        family_id=family_id,
        family_description=family.description,
        lock_protocol_type=family.lock_protocol_type,
        canonical_questions=(
            "\n".join(f"  - {q}" for q in canonical_questions)
            if canonical_questions
            else "  (none yet)"
        ),
        accepted_methods=", ".join(accepted_methods) if accepted_methods else "Any",
        source_cards=source_card_text if source_card_text else "  (none registered)",
    )

    response = await provider.complete(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.85,
        max_tokens=8192,
    )

    ideas = _parse_json_array(response)

    # Validate and normalise each idea card
    validated: list[dict[str, Any]] = []
    for raw in ideas[:count]:
        card = _normalise_idea_card(raw, family_id)
        validated.append(card)

    logger.info(
        "Scout generated %d idea cards for family %s", len(validated), family_id
    )
    return validated


async def screen_idea(
    session: AsyncSession,
    idea_card: dict[str, Any],
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Screen an idea card on 6 dimensions (0-5 scale).

    Returns screening scores + pass/fail.
    Minimum requirements: weighted composite >= 4.0, novelty >= 4,
    data_adequacy >= 4.
    """
    idea_yaml = yaml.dump(idea_card, default_flow_style=False, sort_keys=False)

    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    prompt = SCREEN_USER_PROMPT.format(idea_yaml=idea_yaml)

    response = await provider.complete(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.3,
        max_tokens=2048,
    )

    screening = _parse_json_object(response)

    # Recompute the composite to guard against LLM arithmetic errors
    scores = screening.get("scores", {})
    weighted = 0.0
    for dim, weight in SCREEN_WEIGHTS.items():
        dim_data = scores.get(dim, {})
        score_val = dim_data.get("score", 0) if isinstance(dim_data, dict) else 0
        weighted += score_val * weight

    screening["weighted_composite"] = round(weighted, 3)

    # Enforce minimum thresholds
    novelty_score = _extract_score(scores, "novelty")
    data_score = _extract_score(scores, "data_adequacy")
    passed = (
        weighted >= 4.0
        and novelty_score >= 4
        and data_score >= 4
    )
    screening["pass"] = passed

    logger.info(
        "Scout screened idea (composite=%.2f, novelty=%d, data=%d, pass=%s)",
        weighted,
        novelty_score,
        data_score,
        passed,
    )
    return screening


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_family(session: AsyncSession, family_id: str) -> PaperFamily:
    stmt = select(PaperFamily).where(PaperFamily.id == family_id)
    result = await session.execute(stmt)
    family = result.scalar_one_or_none()
    if family is None:
        raise ValueError(f"Paper family '{family_id}' not found.")
    return family


def _parse_json_field(field_value: str | None, default: Any) -> Any:
    """Safely parse a JSON-encoded model field."""
    if not field_value:
        return default
    try:
        return json.loads(field_value)
    except (json.JSONDecodeError, TypeError):
        return default


def _parse_json_array(response: str) -> list[dict]:
    """Extract a JSON array from an LLM response string."""
    try:
        start = response.index("[")
        end = response.rindex("]") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse idea array from LLM response")
        return []


def _parse_json_object(response: str) -> dict:
    """Extract a JSON object from an LLM response string."""
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse screening object from LLM response")
        return {"scores": {}, "weighted_composite": 0.0, "pass": False, "summary": "Parse error"}


def _normalise_idea_card(raw: dict, family_id: str) -> dict[str, Any]:
    """Ensure an idea card has all required fields with correct types."""
    return {
        "research_question": raw.get("research_question", ""),
        "primary_family": raw.get("primary_family", family_id),
        "secondary_family": raw.get("secondary_family"),
        "public_data_inventory": raw.get("public_data_inventory", []),
        "expected_unit_of_analysis": raw.get("expected_unit_of_analysis", ""),
        "novelty_delta": raw.get("novelty_delta", ""),
        "central_inferential_risk": raw.get("central_inferential_risk", ""),
        "kill_conditions": raw.get("kill_conditions", []),
    }


def _extract_score(scores: dict, dimension: str) -> int:
    """Safely extract a numeric score from the screening scores dict."""
    dim_data = scores.get(dimension, {})
    if isinstance(dim_data, dict):
        return int(dim_data.get("score", 0))
    return 0
