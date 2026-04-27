import json
import logging
from dataclasses import dataclass

from app.services.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default (fallback) system prompt — used when no family-specific rubric exists
# ---------------------------------------------------------------------------
JUDGE_SYSTEM_PROMPT = """You are a senior journal editor evaluating two research papers in a head-to-head comparison.

Evaluate the papers on these criteria:

REWARDED:
- Novel research questions that challenge conventional wisdom
- Rigorous identification strategy (even with null results)
- Honest engagement with limitations
- Appropriate scope and policy relevance
- Clear data sources and transparent methodology

PENALIZED:
- Weak identification strategy
- Failed placebo tests or violated assumptions
- Shallow analysis lacking robustness checks
- Poor execution quality
- Fabricated or suspicious results

IMPORTANT: Evaluate papers solely on their intellectual and methodological merit.
Ignore journal branding, author prestige, or institutional affiliation.
This is a blinded evaluation.

Compare Paper A and Paper B. Consider the overall quality, rigor, and contribution of each paper.

Respond with EXACTLY one of these three options:
- "PAPER_A" if Paper A is clearly better
- "PAPER_B" if Paper B is clearly better
- "DRAW" if the papers are of comparable quality

Provide a brief justification (2-3 sentences) followed by your verdict on a new line."""


# ---------------------------------------------------------------------------
# Family-specific prompt builder
# ---------------------------------------------------------------------------


def get_family_judge_prompt(family) -> str:
    """Build a family-specific judge system prompt.

    Loads evaluation criteria from ``PaperFamily.review_rubric``,
    fatal failures as instant-lose conditions, and mandatory checks as
    important evaluation dimensions.

    Parameters
    ----------
    family : PaperFamily
        The family ORM object (must have ``review_rubric``, ``fatal_failures``,
        ``mandatory_checks``, and ``venue_ladder`` text columns, each holding
        JSON or ``None``).

    Returns
    -------
    str
        A fully-formed system prompt for the LLM judge.
    """
    # --- parse JSON fields safely ---
    rubric = _safe_json(family.review_rubric, {})
    fatal_failures = _safe_json(family.fatal_failures, [])
    mandatory_checks = _safe_json(family.mandatory_checks, [])
    venue_ladder = _safe_json(family.venue_ladder, {})

    # --- header ---
    lines = [
        f"You are a senior journal editor specialising in **{family.name}** research.",
        "",
        "You are conducting a blinded head-to-head evaluation of two papers.",
        "Ignore journal branding, author prestige, or institutional affiliation.",
        "",
    ]

    # --- family-specific evaluation criteria ---
    if rubric:
        lines.append("## Evaluation Criteria and Weights")
        criteria_list = rubric.get("criteria", rubric if isinstance(rubric, list) else [])
        if isinstance(rubric, dict) and "criteria" not in rubric:
            # rubric might be {"criterion_name": weight, ...}
            criteria_list = [
                {"name": k, "weight": v} for k, v in rubric.items() if k not in ("criteria",)
            ]
        for item in criteria_list:
            if isinstance(item, dict):
                name = item.get("name", item.get("criterion", ""))
                weight = item.get("weight", "")
                desc = item.get("description", "")
                line = f"- **{name}**"
                if weight:
                    line += f" (weight: {weight})"
                if desc:
                    line += f": {desc}"
                lines.append(line)
            else:
                lines.append(f"- {item}")
        lines.append("")

    # --- fatal failures (instant-lose) ---
    if fatal_failures:
        lines.append("## Fatal Failures (instant-lose conditions)")
        lines.append("If either paper exhibits ANY of the following, it MUST lose:")
        for ff in fatal_failures:
            if isinstance(ff, dict):
                lines.append(f"- **{ff.get('name', '')}**: {ff.get('description', '')}")
            else:
                lines.append(f"- {ff}")
        lines.append("")

    # --- mandatory checks ---
    if mandatory_checks:
        lines.append("## Mandatory Checks (important evaluation dimensions)")
        lines.append("You MUST explicitly assess each paper on these dimensions:")
        for mc in mandatory_checks:
            if isinstance(mc, dict):
                lines.append(f"- **{mc.get('name', '')}**: {mc.get('description', '')}")
            else:
                lines.append(f"- {mc}")
        lines.append("")

    # --- venue context ---
    if venue_ladder:
        flagship = venue_ladder.get("flagship", [])
        if flagship:
            lines.append(
                f"## Publication Context\n"
                f"Target venues: {', '.join(flagship[:5])}.\n"
                f"Judge quality against the standards of these venues.\n"
            )

    # --- verdict instructions ---
    lines.extend(
        [
            "## Verdict",
            "Compare Paper A and Paper B on the criteria above.",
            "",
            "Respond with EXACTLY one of these three options:",
            '- "PAPER_A" if Paper A is clearly better',
            '- "PAPER_B" if Paper B is clearly better',
            '- "DRAW" if the papers are of comparable quality',
            "",
            "Provide a brief justification (2-3 sentences) then your verdict on a new line.",
        ]
    )

    return "\n".join(lines)


def _safe_json(text: str | None, default):
    """Parse a JSON text column, returning *default* on failure."""
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class JudgmentResult:
    winner: str  # "a_wins", "b_wins", "draw"
    reasoning: str
    raw_response: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_judgment(response: str) -> str:
    """Parse the LLM response to extract the verdict."""
    response_upper = response.upper()
    # Check last 200 chars for the verdict (it should be at the end)
    tail = response_upper[-200:]

    if "PAPER_A" in tail:
        return "a_wins"
    elif "PAPER_B" in tail:
        return "b_wins"
    elif "DRAW" in tail:
        return "draw"

    # Fallback: check full response
    if "PAPER_A" in response_upper:
        return "a_wins"
    elif "PAPER_B" in response_upper:
        return "b_wins"
    else:
        return "draw"


# ---------------------------------------------------------------------------
# Core judge function
# ---------------------------------------------------------------------------


async def judge_match(
    provider: LLMProvider,
    model: str,
    paper_a_content: str,
    paper_b_content: str,
    paper_a_title: str = "Paper A",
    paper_b_title: str = "Paper B",
    custom_criteria: dict | None = None,
    system_prompt_override: str | None = None,
) -> tuple[JudgmentResult, JudgmentResult]:
    """Run position-swapped judgment on two papers.

    If *system_prompt_override* is provided (e.g. a family-specific prompt),
    it replaces the default system prompt entirely.  The legacy
    *custom_criteria* mechanism is only applied when no override is given.

    Returns (result_a_first, result_b_first) where each is a JudgmentResult.
    """
    if system_prompt_override:
        system_prompt = system_prompt_override
    else:
        system_prompt = JUDGE_SYSTEM_PROMPT
        if custom_criteria:
            rewards = custom_criteria.get("rewards", [])
            penalties = custom_criteria.get("penalties", [])
            if rewards:
                system_prompt += "\n\nAdditional rewards:\n" + "\n".join(f"- {r}" for r in rewards)
            if penalties:
                system_prompt += "\n\nAdditional penalties:\n" + "\n".join(
                    f"- {p}" for p in penalties
                )

    # Round 1: Paper A first
    prompt_a_first = f"""## Paper A: {paper_a_title}

{paper_a_content}

---

## Paper B: {paper_b_title}

{paper_b_content}

---

Which paper is better? Provide your justification and verdict."""

    # Round 2: Paper B first
    prompt_b_first = f"""## Paper A: {paper_b_title}

{paper_b_content}

---

## Paper B: {paper_a_title}

{paper_a_content}

---

Which paper is better? Provide your justification and verdict."""

    response_a_first = await provider.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_a_first},
        ],
        model=model,
    )

    response_b_first = await provider.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_b_first},
        ],
        model=model,
    )

    # Parse round 1 (A shown first)
    verdict_a_first = parse_judgment(response_a_first)

    # Parse round 2 (B shown first) - need to reverse the labels
    raw_verdict_b_first = parse_judgment(response_b_first)
    # In round 2, "Paper A" position contains paper B content, so reverse
    if raw_verdict_b_first == "a_wins":
        verdict_b_first = "b_wins"  # "Paper A" won but that was actually paper B
    elif raw_verdict_b_first == "b_wins":
        verdict_b_first = "a_wins"  # "Paper B" won but that was actually paper A
    else:
        verdict_b_first = "draw"

    result_a_first = JudgmentResult(
        winner=verdict_a_first,
        reasoning=response_a_first[:500],
        raw_response=response_a_first,
    )
    result_b_first = JudgmentResult(
        winner=verdict_b_first,
        reasoning=response_b_first[:500],
        raw_response=response_b_first,
    )

    return result_a_first, result_b_first


def resolve_match(result_a_first: str, result_b_first: str) -> str:
    """Resolve final match result from position-swapped judgments.

    Both rounds must agree for a decisive result. Disagreement = draw.
    """
    if result_a_first == result_b_first:
        return result_a_first
    # Disagreement -> draw
    return "draw"
