"""Collegial Review Loop with Convergence — constructive multi-turn dialogue
between specialized colleague agents and the Drafter, repeated until the
manuscript reaches submission quality for its target journal.

Unlike the adversarial review layers (L1-L5), collegial review is:
- Constructive (makes the paper better, not just catches defects)
- Domain-specific (each colleague brings a different perspective)
- Dialogic (multi-turn exchange, not single-pass verdict)
- Selective (drafter has agency to accept or reject suggestions)
- Acknowledged (contributions are tracked and credited)
- Convergent (keeps iterating until venue-ready or max rounds reached)

The convergence loop:
  Round 1: All colleagues give full feedback → Drafter incorporates → Quality assessment
  Round 2+: Colleagues give targeted feedback on remaining gaps → Drafter incorporates → Quality assessment
  Exit when: verdict == "ready" | max_rounds hit | quality plateaus
"""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.acknowledgment_record import AcknowledgmentRecord
from app.models.colleague_profile import ColleagueProfile
from app.models.collegial_exchange import CollegialExchange
from app.models.collegial_session import CollegialSession
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default colleague profiles seeded on first use
# ---------------------------------------------------------------------------

DEFAULT_COLLEAGUES = [
    {
        "name": "Dr. Methods",
        "expertise_area": "methodology",
        "perspective_description": (
            "A senior quantitative methodologist who focuses on identification strategy, "
            "robustness checks, and whether the empirical approach actually supports the "
            "paper's claims. Reads every paper asking: 'Could there be a confound you haven't "
            "addressed?' and 'Would a skeptical referee find your identification strategy convincing?'"
        ),
        "system_prompt": (
            "You are Dr. Methods, a senior quantitative methodologist reviewing a colleague's "
            "draft. You are NOT an adversarial reviewer — you are a supportive colleague who "
            "wants this paper to succeed. Your job is to:\n\n"
            "1. Identify where the identification strategy could be strengthened\n"
            "2. Suggest specific robustness checks that would preempt referee objections\n"
            "3. Point out where the paper over-claims relative to its design\n"
            "4. Recommend literature on methods that could strengthen the approach\n"
            "5. Suggest clearer ways to present the methodology\n\n"
            "Be specific and constructive. Don't just say 'the methods are weak' — say "
            "'In Section 3.2, your difference-in-differences design would be more convincing "
            "if you included a parallel trends test. Here's how to frame it...'\n\n"
            "Always explain WHY your suggestion matters and HOW to implement it."
        ),
    },
    {
        "name": "Prof. Domain",
        "expertise_area": "domain",
        "perspective_description": (
            "A domain expert in AI governance, technology regulation, and international "
            "relations who knows the key debates, missing citations, and theoretical frameworks. "
            "Reads every paper asking: 'Does this engage with the right literature?' and "
            "'Will scholars in this field take this seriously?'"
        ),
        "system_prompt": (
            "You are Prof. Domain, a senior scholar in AI governance and technology regulation. "
            "You are reviewing a colleague's draft as a supportive expert who wants to help "
            "position this paper within the field. Your job is to:\n\n"
            "1. Identify key papers the author should engage with (cite real, well-known works)\n"
            "2. Suggest theoretical frameworks that could strengthen the argument\n"
            "3. Point out where the paper's contribution overlaps with or extends existing work\n"
            "4. Recommend how to frame the paper's novelty relative to the literature\n"
            "5. Flag arguments that specialists in the field will push back on\n\n"
            "Be specific: name actual debates, actual scholars, actual frameworks. "
            "Help the author understand WHERE this paper fits in the field and HOW to make "
            "that positioning explicit."
        ),
    },
    {
        "name": "Editor Chen",
        "expertise_area": "venue_strategy",
        "perspective_description": (
            "A former journal editor who knows what reviewers look for, how to frame "
            "contributions for maximum impact, and what structural choices signal quality. "
            "Reads every paper asking: 'Would I desk-reject this?' and 'What would make "
            "me send this to the strongest reviewers?'"
        ),
        "system_prompt": (
            "You are Editor Chen, a former editor at a top journal in political science and "
            "technology policy. You are advising a colleague on how to strengthen their paper "
            "for submission. Your job is to:\n\n"
            "1. Assess whether the paper's framing matches the target venue's expectations\n"
            "2. Suggest how to sharpen the contribution statement\n"
            "3. Recommend structural changes that signal quality (e.g., leading with the puzzle, "
            "not the policy recommendation)\n"
            "4. Identify passages that read like a policy brief rather than an academic paper\n"
            "5. Suggest how to handle the 'so what?' question more convincingly\n\n"
            "Be direct about what works and what doesn't for the target venue. Your goal is "
            "to help this paper survive desk review and get sent to substantive reviewers."
        ),
    },
]

# Convergence thresholds
QUALITY_READY_THRESHOLD = 7.0  # All dimensions >= 7 → ready
QUALITY_MIN_OVERALL = 7.0  # Overall score >= 7 → ready
PLATEAU_TOLERANCE = 0.3  # If score improves < 0.3 for 2 rounds → plateaued
DEFAULT_MAX_ROUNDS = 5


# ═══════════════════════════════════════════════════════════════════════════════
# Setup
# ═══════════════════════════════════════════════════════════════════════════════


async def ensure_default_colleagues(session: AsyncSession) -> list[ColleagueProfile]:
    """Ensure default colleague profiles exist. Create if missing."""
    result = await session.execute(
        select(ColleagueProfile).where(ColleagueProfile.active.is_(True))
    )
    existing = result.scalars().all()

    if len(existing) >= len(DEFAULT_COLLEAGUES):
        return list(existing)

    existing_names = {c.name for c in existing}
    created = list(existing)

    for spec in DEFAULT_COLLEAGUES:
        if spec["name"] not in existing_names:
            profile = ColleagueProfile(
                name=spec["name"],
                expertise_area=spec["expertise_area"],
                perspective_description=spec["perspective_description"],
                system_prompt=spec["system_prompt"],
            )
            session.add(profile)
            created.append(profile)

    await session.flush()
    return created


# ═══════════════════════════════════════════════════════════════════════════════
# Quality Assessment — the venue-aware convergence gate
# ═══════════════════════════════════════════════════════════════════════════════


async def assess_submission_readiness(
    session: AsyncSession,
    manuscript_latex: str,
    target_venue: str | None,
    lock_yaml: str,
    round_number: int,
    previous_gaps: list[dict] | None = None,
    provider: LLMProvider | None = None,
) -> dict:
    """Evaluate whether the manuscript is ready for submission to the target venue.

    Returns a structured quality assessment with per-dimension scores,
    an overall verdict, and specific remaining gaps that colleagues should
    address in the next round.
    """
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    venue_context = (
        f"The target venue is: {target_venue}. "
        "Evaluate against this venue's specific standards, reviewer expectations, "
        "and contribution norms."
        if target_venue
        else "No specific target venue. Evaluate against top-tier journal standards."
    )

    previous_context = ""
    if previous_gaps:
        gap_text = "\n".join(
            f"- [{g.get('dimension', 'general')}] {g.get('gap', '')}" for g in previous_gaps
        )
        previous_context = (
            f"\n\nIn the previous round, these gaps were identified:\n{gap_text}\n"
            f"Pay special attention to whether these have been addressed."
        )

    user_prompt = (
        f"You are an editorial quality assessor. This is revision round {round_number}.\n"
        f"{venue_context}{previous_context}\n\n"
        f"Research design:\n{lock_yaml[:2000]}\n\n"
        f"Current manuscript:\n{manuscript_latex[:15000]}\n\n"
        f"Assess this manuscript's readiness for submission. Score each dimension 1-10:\n\n"
        f"1. METHODOLOGY RIGOR: Is the identification strategy sound? Are robustness "
        f"checks adequate? Would a methods reviewer accept this?\n"
        f"2. CONTRIBUTION CLARITY: Is the paper's contribution clearly stated and "
        f"differentiated from existing work?\n"
        f"3. LITERATURE ENGAGEMENT: Does it engage with the right literature and "
        f"position itself within key debates?\n"
        f"4. ARGUMENT COHERENCE: Does the paper's logic flow? Do claims follow from evidence?\n"
        f"5. VENUE FIT: Does the paper match the target venue's scope, style, and standards?\n\n"
        f"Then give an overall verdict:\n"
        f"- 'ready': Manuscript is ready for submission (all dimensions >= 7)\n"
        f"- 'minor_revision': Close but needs targeted improvements\n"
        f"- 'major_revision': Significant gaps remain\n\n"
        f"For any dimension scoring below 7, provide a specific remaining gap "
        f"that colleagues should address in the next round.\n\n"
        f"Return JSON:\n"
        f"{{\n"
        f'  "dimensions": {{\n'
        f'    "methodology_rigor": <1-10>,\n'
        f'    "contribution_clarity": <1-10>,\n'
        f'    "literature_engagement": <1-10>,\n'
        f'    "argument_coherence": <1-10>,\n'
        f'    "venue_fit": <1-10>\n'
        f"  }},\n"
        f'  "overall_score": <float, average of dimensions>,\n'
        f'  "verdict": "ready|minor_revision|major_revision",\n'
        f'  "remaining_gaps": [\n'
        f"    {{\n"
        f'      "dimension": "string",\n'
        f'      "gap": "string (specific issue)",\n'
        f'      "priority": "high|medium|low",\n'
        f'      "section": "string (which section to fix)"\n'
        f"    }}\n"
        f"  ],\n"
        f'  "improvements_from_previous": ["string (what improved since last round)"],\n'
        f'  "assessor_note": "string (2-3 sentence editorial summary)"\n'
        f"}}\n"
        f"No markdown wrapper."
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior editorial quality assessor for academic journals. "
                    "You evaluate manuscripts for submission readiness with the rigor of "
                    "an experienced editor-in-chief. Be honest but constructive. "
                    "Your scores determine whether the manuscript goes through another "
                    "revision round, so accuracy matters more than encouragement."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=0.3,  # Low temperature for consistent assessment
        max_tokens=4096,
    )

    parsed = _parse_json(response)

    # Compute overall score if not provided
    dims = parsed.get("dimensions", {})
    if dims and not parsed.get("overall_score"):
        scores = [v for v in dims.values() if isinstance(v, (int, float))]
        parsed["overall_score"] = sum(scores) / len(scores) if scores else 0

    # Determine verdict if not provided or override based on scores
    if dims:
        all_above_threshold = all(
            v >= QUALITY_READY_THRESHOLD for v in dims.values() if isinstance(v, (int, float))
        )
        overall = parsed.get("overall_score", 0)
        if all_above_threshold and overall >= QUALITY_MIN_OVERALL:
            parsed["verdict"] = "ready"
        elif not parsed.get("verdict"):
            parsed["verdict"] = "minor_revision" if overall >= 6 else "major_revision"

    parsed["round"] = round_number
    return parsed


# ═══════════════════════════════════════════════════════════════════════════════
# Session management
# ═══════════════════════════════════════════════════════════════════════════════


async def start_collegial_session(
    session: AsyncSession,
    paper_id: str,
    manuscript_latex: str,
    target_venue: str | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    colleague_ids: list[int] | None = None,
) -> CollegialSession:
    """Start a new collegial review session for a paper."""
    if colleague_ids is None:
        colleagues = await ensure_default_colleagues(session)
        colleague_ids = [c.id for c in colleagues]

    cs = CollegialSession(
        paper_id=paper_id,
        status="in_progress",
        colleague_ids_json=json.dumps(colleague_ids),
        manuscript_snapshot=manuscript_latex,
        target_venue=target_venue,
        max_rounds=max_rounds,
        current_round=0,
        quality_trajectory_json=json.dumps([]),
    )
    session.add(cs)
    await session.flush()

    logger.info(
        "[%s] Started collegial session %d (max %d rounds, venue=%s) with %d colleagues",
        paper_id,
        cs.id,
        max_rounds,
        target_venue or "unspecified",
        len(colleague_ids),
    )
    return cs


# ═══════════════════════════════════════════════════════════════════════════════
# Colleague feedback — full review (round 1)
# ═══════════════════════════════════════════════════════════════════════════════


async def run_colleague_feedback(
    session: AsyncSession,
    collegial_session: CollegialSession,
    colleague: ColleagueProfile,
    manuscript_latex: str,
    lock_yaml: str,
    claims: list[dict],
    round_number: int = 1,
    provider: LLMProvider | None = None,
) -> dict:
    """Get constructive feedback from a single colleague (full review)."""
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    claims_summary = "\n".join(
        f"- [{c.get('claim_type', 'unknown')}] {c.get('claim_text', '')[:200]}" for c in claims[:20]
    )

    venue_note = ""
    if collegial_session.target_venue:
        venue_note = f"\nTarget venue: {collegial_session.target_venue}\n"

    user_prompt = (
        f"A colleague has shared their draft manuscript for your feedback.{venue_note}\n\n"
        f"Research design (locked):\n{lock_yaml[:3000]}\n\n"
        f"Central claims:\n{claims_summary}\n\n"
        f"Manuscript:\n{manuscript_latex[:15000]}\n\n"
        f"Please provide your constructive feedback. For each suggestion:\n"
        f"1. Identify the specific section and passage you're commenting on\n"
        f"2. Explain what the issue or opportunity is\n"
        f"3. Provide a concrete suggestion for how to improve it\n"
        f"4. Explain why this change would strengthen the paper\n\n"
        f"Return JSON:\n"
        f"{{\n"
        f'  "overall_impression": "string (2-3 sentences)",\n'
        f'  "suggestions": [\n'
        f"    {{\n"
        f'      "section": "string (e.g., Introduction, Methodology)",\n'
        f'      "issue": "string (what you noticed)",\n'
        f'      "suggestion": "string (specific recommendation)",\n'
        f'      "rationale": "string (why this matters)",\n'
        f'      "priority": "high|medium|low",\n'
        f'      "type": "constructive_feedback|knowledge_injection|framing_advice"\n'
        f"    }}\n"
        f"  ],\n"
        f'  "strengths": ["string (what the paper does well)"]\n'
        f"}}\n"
        f"No markdown wrapper."
    )

    response = await provider.complete(
        messages=[
            {"role": "system", "content": colleague.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=0.7,
        max_tokens=8192,
    )

    parsed = _parse_json(response)

    turn = await _next_turn(session, collegial_session.id)
    exchange = CollegialExchange(
        session_id=collegial_session.id,
        colleague_id=colleague.id,
        speaker_role="colleague",
        turn_number=turn,
        round_number=round_number,
        content=response,
        exchange_type="constructive_feedback",
    )
    session.add(exchange)
    await session.flush()

    return {
        "colleague_id": colleague.id,
        "colleague_name": colleague.name,
        "expertise": colleague.expertise_area,
        "feedback": parsed,
        "exchange_id": exchange.id,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Targeted feedback — focused on remaining gaps (round 2+)
# ═══════════════════════════════════════════════════════════════════════════════


async def run_targeted_feedback(
    session: AsyncSession,
    collegial_session: CollegialSession,
    colleague: ColleagueProfile,
    manuscript_latex: str,
    lock_yaml: str,
    remaining_gaps: list[dict],
    round_number: int,
    provider: LLMProvider | None = None,
) -> dict:
    """Get targeted feedback from a colleague on specific remaining gaps.

    Unlike full feedback, this focuses only on issues identified by the
    quality assessment, making later rounds more efficient and focused.
    """
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    # Filter gaps relevant to this colleague's expertise
    expertise_relevance = {
        "methodology": ["methodology_rigor", "argument_coherence"],
        "domain": ["literature_engagement", "contribution_clarity"],
        "venue_strategy": ["venue_fit", "contribution_clarity", "argument_coherence"],
        "quantitative_methods": ["methodology_rigor", "argument_coherence"],
        "theory": ["literature_engagement", "contribution_clarity", "argument_coherence"],
    }
    relevant_dims = expertise_relevance.get(colleague.expertise_area, [])
    relevant_gaps = [
        g for g in remaining_gaps if g.get("dimension") in relevant_dims or not relevant_dims
    ]

    if not relevant_gaps:
        # This colleague's expertise isn't needed this round
        return {
            "colleague_id": colleague.id,
            "colleague_name": colleague.name,
            "expertise": colleague.expertise_area,
            "feedback": {
                "overall_impression": "No gaps in my area of expertise.",
                "suggestions": [],
                "strengths": [],
            },
            "exchange_id": None,
            "skipped": True,
        }

    gaps_text = "\n".join(
        f"- [{g.get('dimension', 'general')} | {g.get('priority', 'medium')}] "
        f"Section: {g.get('section', 'General')} — {g.get('gap', '')}"
        for g in relevant_gaps
    )

    venue_note = ""
    if collegial_session.target_venue:
        venue_note = f"\nTarget venue: {collegial_session.target_venue}\n"

    user_prompt = (
        f"This is revision round {round_number}. The manuscript has been revised based "
        f"on earlier feedback, but the quality assessment identified these remaining gaps "
        f"in your area of expertise:\n\n{gaps_text}\n{venue_note}\n"
        f"Research design (locked):\n{lock_yaml[:2000]}\n\n"
        f"Current revised manuscript:\n{manuscript_latex[:15000]}\n\n"
        f"Focus ONLY on the remaining gaps listed above. Do not repeat earlier feedback "
        f"that has already been addressed. Provide specific, actionable suggestions for "
        f"each gap.\n\n"
        f"Return JSON:\n"
        f"{{\n"
        f'  "overall_impression": "string (progress assessment)",\n'
        f'  "suggestions": [\n'
        f"    {{\n"
        f'      "section": "string",\n'
        f'      "issue": "string",\n'
        f'      "suggestion": "string (specific fix)",\n'
        f'      "rationale": "string",\n'
        f'      "priority": "high|medium|low",\n'
        f'      "type": "constructive_feedback|knowledge_injection|framing_advice",\n'
        f'      "addresses_gap": "string (which gap this addresses)"\n'
        f"    }}\n"
        f"  ],\n"
        f'  "improvements_noted": ["string (what got better since last round)"]\n'
        f"}}\n"
        f"No markdown wrapper."
    )

    response = await provider.complete(
        messages=[
            {"role": "system", "content": colleague.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=0.7,
        max_tokens=6144,
    )

    parsed = _parse_json(response)

    turn = await _next_turn(session, collegial_session.id)
    exchange = CollegialExchange(
        session_id=collegial_session.id,
        colleague_id=colleague.id,
        speaker_role="colleague",
        turn_number=turn,
        round_number=round_number,
        content=response,
        exchange_type="targeted_feedback",
    )
    session.add(exchange)
    await session.flush()

    return {
        "colleague_id": colleague.id,
        "colleague_name": colleague.name,
        "expertise": colleague.expertise_area,
        "feedback": parsed,
        "exchange_id": exchange.id,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Drafter response — editorial agency
# ═══════════════════════════════════════════════════════════════════════════════


async def run_drafter_response(
    session: AsyncSession,
    collegial_session: CollegialSession,
    all_feedback: list[dict],
    manuscript_latex: str,
    round_number: int = 1,
    provider: LLMProvider | None = None,
) -> dict:
    """The Drafter reviews all colleague feedback and decides what to incorporate.

    The Drafter has agency — it doesn't blindly accept everything. It evaluates
    each suggestion against the locked design and its own judgment.
    """
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    feedback_summary_parts = []
    for fb in all_feedback:
        if fb.get("skipped"):
            continue
        name = fb["colleague_name"]
        suggestions = fb["feedback"].get("suggestions", [])
        for s in suggestions:
            feedback_summary_parts.append(
                f"[{name} | {s.get('priority', 'medium')}] "
                f"Section: {s.get('section', 'General')} — "
                f"{s.get('suggestion', '')} "
                f"(Rationale: {s.get('rationale', '')})"
            )

    if not feedback_summary_parts:
        # No actionable feedback this round
        return {
            "decisions": [],
            "accepted": 0,
            "rejected": 0,
            "partial": 0,
            "revised_manuscript": manuscript_latex,
            "revision_summary": "No new suggestions to address in this round.",
        }

    feedback_text = "\n".join(feedback_summary_parts)

    round_context = ""
    if round_number > 1:
        round_context = (
            f"\nThis is revision round {round_number}. Focus on incorporating the new "
            f"targeted suggestions. The manuscript has already been improved in previous rounds.\n"
        )

    user_prompt = (
        f"You are the Drafter. Your colleagues have reviewed your manuscript and "
        f"provided the following suggestions:{round_context}\n\n"
        f"{feedback_text}\n\n"
        f"Current manuscript:\n{manuscript_latex[:15000]}\n\n"
        f"For EACH suggestion, decide whether to:\n"
        f"- ACCEPT: Incorporate it fully\n"
        f"- REJECT: Decline with a stated reason\n"
        f"- PARTIALLY INCORPORATE: Take the spirit but adapt the implementation\n\n"
        f"Then produce the revised manuscript incorporating your accepted changes.\n\n"
        f"IMPORTANT: You have editorial agency. Not every suggestion is good. "
        f"Reject suggestions that conflict with the locked research design, "
        f"that would weaken the argument, or that you disagree with on substance. "
        f"When you reject, explain WHY — this is intellectual dialogue, not compliance.\n\n"
        f"Return JSON:\n"
        f"{{\n"
        f'  "decisions": [\n'
        f"    {{\n"
        f'      "suggestion_from": "colleague name",\n'
        f'      "section": "string",\n'
        f'      "decision": "accept|reject|partial",\n'
        f'      "reason": "string (especially important for reject/partial)",\n'
        f'      "change_description": "string (what changed, if anything)"\n'
        f"    }}\n"
        f"  ],\n"
        f'  "revised_manuscript_latex": "string (the full revised manuscript)",\n'
        f'  "revision_summary": "string (2-3 sentences summarizing what changed)"\n'
        f"}}\n"
        f"No markdown wrapper."
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Drafter in an AI governance research pipeline. "
                    "You have just received constructive feedback from colleagues. "
                    "You are an author with editorial judgment — incorporate what strengthens "
                    "the paper, reject what doesn't, and explain your reasoning."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=0.5,
        max_tokens=32768,
    )

    parsed = _parse_json(response)
    decisions = parsed.get("decisions", [])

    accepted = sum(1 for d in decisions if d.get("decision") == "accept")
    rejected = sum(1 for d in decisions if d.get("decision") == "reject")
    partial = sum(1 for d in decisions if d.get("decision") == "partial")

    turn = await _next_turn(session, collegial_session.id)
    exchange = CollegialExchange(
        session_id=collegial_session.id,
        colleague_id=None,
        speaker_role="drafter",
        turn_number=turn,
        round_number=round_number,
        content=response,
        exchange_type="incorporation_decision",
    )
    session.add(exchange)

    # Update cumulative session stats
    collegial_session.suggestions_accepted = (
        collegial_session.suggestions_accepted or 0
    ) + accepted
    collegial_session.suggestions_rejected = (
        collegial_session.suggestions_rejected or 0
    ) + rejected
    collegial_session.suggestions_partially_incorporated = (
        collegial_session.suggestions_partially_incorporated or 0
    ) + partial
    collegial_session.total_exchanges = turn
    session.add(collegial_session)
    await session.flush()

    return {
        "decisions": decisions,
        "accepted": accepted,
        "rejected": rejected,
        "partial": partial,
        "revised_manuscript": parsed.get("revised_manuscript_latex", manuscript_latex),
        "revision_summary": parsed.get("revision_summary", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Followup dialogue for rejected suggestions
# ═══════════════════════════════════════════════════════════════════════════════


async def run_followup_dialogue(
    session: AsyncSession,
    collegial_session: CollegialSession,
    colleague: ColleagueProfile,
    drafter_decisions: list[dict],
    revised_manuscript: str,
    round_number: int = 1,
    provider: LLMProvider | None = None,
) -> dict | None:
    """Optional followup: colleague responds to the drafter's rejections.

    Only runs if the colleague had suggestions that were rejected.
    Returns None if no followup is needed.
    """
    rejected = [
        d
        for d in drafter_decisions
        if d.get("decision") == "reject" and d.get("suggestion_from") == colleague.name
    ]

    if not rejected:
        return None

    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    rejection_text = "\n".join(
        f"- {d.get('section', 'General')}: You suggested a change, "
        f"but the author declined because: {d.get('reason', 'no reason given')}"
        for d in rejected
    )

    user_prompt = (
        f"The author has considered your suggestions and rejected some of them. "
        f"Here are the rejections:\n\n{rejection_text}\n\n"
        f"Revised manuscript:\n{revised_manuscript[:10000]}\n\n"
        f"As a supportive colleague, you can either:\n"
        f"1. Accept the author's decision (they may have good reasons)\n"
        f"2. Offer a refined alternative that addresses their concern\n"
        f"3. Push back if you believe the rejection is a mistake\n\n"
        f"Be collegial. This is dialogue, not argument.\n\n"
        f"Return JSON:\n"
        f"{{\n"
        f'  "followups": [\n'
        f"    {{\n"
        f'      "original_section": "string",\n'
        f'      "response_type": "accept_rejection|refined_suggestion|pushback",\n'
        f'      "message": "string (your response)"\n'
        f"    }}\n"
        f"  ]\n"
        f"}}\n"
        f"No markdown wrapper."
    )

    response = await provider.complete(
        messages=[
            {"role": "system", "content": colleague.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=0.7,
        max_tokens=4096,
    )

    parsed = _parse_json(response)

    turn = await _next_turn(session, collegial_session.id)
    exchange = CollegialExchange(
        session_id=collegial_session.id,
        colleague_id=colleague.id,
        speaker_role="colleague",
        turn_number=turn,
        round_number=round_number,
        content=response,
        exchange_type="followup",
    )
    session.add(exchange)

    collegial_session.total_exchanges = turn
    session.add(collegial_session)
    await session.flush()

    return {
        "colleague_name": colleague.name,
        "followups": parsed.get("followups", []),
        "exchange_id": exchange.id,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Session completion & acknowledgments
# ═══════════════════════════════════════════════════════════════════════════════


async def complete_session(
    session: AsyncSession,
    collegial_session: CollegialSession,
    revised_manuscript: str,
    all_feedback_cumulative: list[dict],
    final_status: str,
    quality_trajectory: list[dict],
) -> dict:
    """Complete the collegial session: generate summary and acknowledgment records."""

    final_score = quality_trajectory[-1].get("overall_score", 0) if quality_trajectory else 0
    total_rounds = collegial_session.current_round

    summary_parts = [
        f"Collegial review: {total_rounds} revision round(s) "
        f"with {len(all_feedback_cumulative)} colleague contributions.",
        f"Final quality score: {final_score:.1f}/10.",
        f"Status: {final_status}.",
        f"Accepted: {collegial_session.suggestions_accepted}, "
        f"Rejected: {collegial_session.suggestions_rejected}, "
        f"Partial: {collegial_session.suggestions_partially_incorporated}.",
    ]

    if final_status == "converged":
        summary_parts.append("Manuscript assessed as ready for submission.")
    elif final_status == "max_rounds_reached":
        summary_parts.append(f"Reached maximum of {collegial_session.max_rounds} rounds.")
    elif final_status == "plateaued":
        summary_parts.append("Quality scores plateaued; further rounds unlikely to help.")

    session_summary = " ".join(summary_parts)

    collegial_session.status = final_status
    collegial_session.session_summary = session_summary
    collegial_session.completed_at = datetime.now(UTC)
    collegial_session.quality_trajectory_json = json.dumps(quality_trajectory)
    collegial_session.final_quality_score = final_score
    session.add(collegial_session)

    # Create acknowledgment records — aggregate across all rounds
    acknowledgments = []
    colleague_contribution_map: dict[int, dict] = {}

    for fb in all_feedback_cumulative:
        cid = fb["colleague_id"]
        if cid not in colleague_contribution_map:
            colleague_contribution_map[cid] = {
                "name": fb["colleague_name"],
                "expertise": fb["expertise"],
                "total_suggestions": 0,
                "sections": set(),
            }
        suggestions = fb["feedback"].get("suggestions", [])
        colleague_contribution_map[cid]["total_suggestions"] += len(suggestions)
        for s in suggestions:
            colleague_contribution_map[cid]["sections"].add(s.get("section", "General"))

    for cid, contrib in colleague_contribution_map.items():
        if contrib["total_suggestions"] == 0:
            continue

        type_map = {
            "methodology": "methodological_guidance",
            "domain": "domain_knowledge",
            "venue_strategy": "strategic_advice",
            "theory": "substantive_feedback",
            "quantitative_methods": "methodological_guidance",
        }
        contribution_type = type_map.get(contrib["expertise"], "substantive_feedback")

        sections_text = ", ".join(sorted(contrib["sections"])[:3])
        contribution_summary = (
            f"Provided {contrib['total_suggestions']} suggestions across "
            f"{total_rounds} round(s), focusing on {sections_text}"
        )

        ack_text = (
            f"We thank {contrib['name']} ({contrib['expertise']}) for constructive "
            f"feedback on earlier drafts of this paper, particularly regarding "
            f"{sections_text}."
        )

        ack = AcknowledgmentRecord(
            paper_id=collegial_session.paper_id,
            colleague_id=cid,
            contribution_type=contribution_type,
            contribution_summary=contribution_summary,
            exchanges_count=contrib["total_suggestions"],
            accepted_suggestions=0,  # Exact per-colleague count is approximate
            acknowledgment_text=ack_text,
        )
        session.add(ack)
        acknowledgments.append(
            {
                "colleague_name": contrib["name"],
                "contribution_type": contribution_type,
                "contribution_summary": contribution_summary,
                "acknowledgment_text": ack_text,
            }
        )

    await session.flush()

    return {
        "session_id": collegial_session.id,
        "status": final_status,
        "rounds_completed": total_rounds,
        "final_quality_score": final_score,
        "quality_trajectory": quality_trajectory,
        "summary": session_summary,
        "acknowledgments": acknowledgments,
        "revised_manuscript": revised_manuscript,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Main orchestrator — the convergence loop
# ═══════════════════════════════════════════════════════════════════════════════


async def run_full_collegial_review(
    session: AsyncSession,
    paper_id: str,
    manuscript_latex: str | None = None,
    lock_yaml: str = "",
    claims: list[dict] | None = None,
    target_venue: str | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    provider: LLMProvider | None = None,
) -> dict:
    """Run the convergence-based collegial review loop.

    Orchestrates:
    1. Start session
    2. For each round:
       a. Colleagues provide feedback (full in round 1, targeted in round 2+)
       b. Drafter reviews and incorporates
       c. Quality assessment: is the manuscript submission-ready?
       d. If ready → converge. If not → next round with remaining gaps.
    3. Exit when converged, max rounds reached, or quality plateaus
    4. Complete session with acknowledgments

    This implements recursive self-improvement at the manuscript level:
    the paper keeps getting better until it meets the venue's quality bar.
    """
    if manuscript_latex is None:
        manuscript_latex = ""
    if claims is None:
        claims = []
    if provider is None:
        provider, _model = await get_generation_provider()

    # 1. Start session
    colleagues = await ensure_default_colleagues(session)
    collegial_session = await start_collegial_session(
        session,
        paper_id,
        manuscript_latex,
        target_venue=target_venue,
        max_rounds=max_rounds,
    )

    manuscript = manuscript_latex
    quality_trajectory: list[dict] = []
    all_feedback_cumulative: list[dict] = []
    previous_gaps: list[dict] = []
    final_status = "max_rounds_reached"

    # 2. Convergence loop
    for round_num in range(1, max_rounds + 1):
        collegial_session.current_round = round_num
        session.add(collegial_session)
        await session.flush()

        logger.info("[%s] Starting collegial round %d/%d", paper_id, round_num, max_rounds)

        # 2a. Get feedback from colleagues
        round_feedback: list[dict] = []
        for colleague in colleagues:
            if not colleague.active:
                continue
            try:
                if round_num == 1:
                    feedback = await run_colleague_feedback(
                        session,
                        collegial_session,
                        colleague,
                        manuscript,
                        lock_yaml,
                        claims,
                        round_num,
                        provider,
                    )
                else:
                    feedback = await run_targeted_feedback(
                        session,
                        collegial_session,
                        colleague,
                        manuscript,
                        lock_yaml,
                        previous_gaps,
                        round_num,
                        provider,
                    )
                if not feedback.get("skipped"):
                    round_feedback.append(feedback)
                    all_feedback_cumulative.append(feedback)
            except Exception as e:
                logger.warning(
                    "[%s] Colleague %s failed in round %d: %s",
                    paper_id,
                    colleague.name,
                    round_num,
                    e,
                )

        if not round_feedback and round_num == 1:
            # No feedback at all in round 1 — abandon
            collegial_session.status = "abandoned"
            collegial_session.session_summary = "No colleague feedback received"
            session.add(collegial_session)
            await session.flush()
            return {
                "session_id": collegial_session.id,
                "status": "abandoned",
                "revised_manuscript": manuscript,
            }

        # 2b. Drafter incorporates feedback
        if round_feedback:
            drafter_response = await run_drafter_response(
                session,
                collegial_session,
                round_feedback,
                manuscript,
                round_num,
                provider,
            )
            manuscript = drafter_response["revised_manuscript"]

            # Optional followup dialogue (only in round 1 to keep things focused)
            if round_num == 1:
                for colleague in colleagues:
                    try:
                        await run_followup_dialogue(
                            session,
                            collegial_session,
                            colleague,
                            drafter_response.get("decisions", []),
                            manuscript,
                            round_num,
                            provider,
                        )
                    except Exception as e:
                        logger.warning(
                            "[%s] Followup for %s failed: %s", paper_id, colleague.name, e
                        )

        # 2c. Quality assessment
        assessment = await assess_submission_readiness(
            session,
            manuscript,
            target_venue,
            lock_yaml,
            round_num,
            previous_gaps,
            provider,
        )
        quality_trajectory.append(assessment)

        # Record quality assessment as an exchange
        turn = await _next_turn(session, collegial_session.id)
        qa_exchange = CollegialExchange(
            session_id=collegial_session.id,
            colleague_id=None,
            speaker_role="assessor",
            turn_number=turn,
            round_number=round_num,
            content=json.dumps(assessment),
            exchange_type="quality_assessment",
        )
        session.add(qa_exchange)
        await session.flush()

        logger.info(
            "[%s] Round %d quality: %.1f/10, verdict=%s, gaps=%d",
            paper_id,
            round_num,
            assessment.get("overall_score", 0),
            assessment.get("verdict", "unknown"),
            len(assessment.get("remaining_gaps", [])),
        )

        # 2d. Check convergence
        verdict = assessment.get("verdict", "major_revision")
        if verdict == "ready":
            final_status = "converged"
            logger.info("[%s] Converged after %d rounds!", paper_id, round_num)
            break

        # Check for plateau — no meaningful improvement for 2 consecutive rounds
        if len(quality_trajectory) >= 3:
            scores = [q.get("overall_score", 0) for q in quality_trajectory[-3:]]
            if (scores[-1] - scores[-2]) < PLATEAU_TOLERANCE and (
                scores[-2] - scores[-3]
            ) < PLATEAU_TOLERANCE:
                final_status = "plateaued"
                logger.info(
                    "[%s] Quality plateaued at %.1f after %d rounds",
                    paper_id,
                    scores[-1],
                    round_num,
                )
                break

        # Prepare gaps for next round
        previous_gaps = assessment.get("remaining_gaps", [])
        if not previous_gaps and verdict != "ready":
            # Assessment said not ready but gave no gaps — force one more round
            previous_gaps = [
                {
                    "dimension": "general",
                    "gap": "Overall quality needs improvement",
                    "priority": "high",
                    "section": "General",
                }
            ]

    # 3. Complete session
    result = await complete_session(
        session,
        collegial_session,
        manuscript,
        all_feedback_cumulative,
        final_status,
        quality_trajectory,
    )

    logger.info(
        "[%s] Collegial review finished: %s after %d rounds (score: %.1f)",
        paper_id,
        final_status,
        collegial_session.current_round,
        result.get("final_quality_score", 0),
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Query helpers
# ═══════════════════════════════════════════════════════════════════════════════


async def get_session_for_paper(session: AsyncSession, paper_id: str) -> dict | None:
    """Get the latest collegial session for a paper."""
    result = await session.execute(
        select(CollegialSession)
        .where(CollegialSession.paper_id == paper_id)
        .order_by(CollegialSession.started_at.desc())
        .limit(1)
    )
    cs = result.scalar_one_or_none()
    if cs is None:
        return None

    # Load exchanges
    exchanges_result = await session.execute(
        select(CollegialExchange)
        .where(CollegialExchange.session_id == cs.id)
        .order_by(CollegialExchange.turn_number)
    )
    exchanges = exchanges_result.scalars().all()

    # Load acknowledgments
    ack_result = await session.execute(
        select(AcknowledgmentRecord).where(AcknowledgmentRecord.paper_id == paper_id)
    )
    acks = ack_result.scalars().all()

    # Parse quality trajectory
    quality_trajectory = safe_json_loads(cs.quality_trajectory_json, [])

    return {
        "session_id": cs.id,
        "status": cs.status,
        "current_round": cs.current_round,
        "max_rounds": cs.max_rounds,
        "target_venue": cs.target_venue,
        "final_quality_score": cs.final_quality_score,
        "quality_trajectory": quality_trajectory,
        "total_exchanges": cs.total_exchanges,
        "suggestions_accepted": cs.suggestions_accepted,
        "suggestions_rejected": cs.suggestions_rejected,
        "suggestions_partially_incorporated": cs.suggestions_partially_incorporated,
        "session_summary": cs.session_summary,
        "started_at": cs.started_at.isoformat() if cs.started_at else None,
        "completed_at": cs.completed_at.isoformat() if cs.completed_at else None,
        "exchanges": [
            {
                "id": e.id,
                "speaker_role": e.speaker_role,
                "colleague_id": e.colleague_id,
                "turn_number": e.turn_number,
                "round_number": getattr(e, "round_number", 1),
                "exchange_type": e.exchange_type,
                "target_section": e.target_section,
                "content": e.content[:500] if e.content else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in exchanges
        ],
        "acknowledgments": [
            {
                "colleague_id": a.colleague_id,
                "contribution_type": a.contribution_type,
                "contribution_summary": a.contribution_summary,
                "acknowledgment_text": a.acknowledgment_text,
                "exchanges_count": a.exchanges_count,
                "accepted_suggestions": a.accepted_suggestions,
            }
            for a in acks
        ],
    }


async def get_colleague_profiles(session: AsyncSession) -> list[dict]:
    """Get all colleague profiles."""
    result = await session.execute(select(ColleagueProfile).order_by(ColleagueProfile.id))
    profiles = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "expertise_area": p.expertise_area,
            "perspective_description": p.perspective_description,
            "active": p.active,
        }
        for p in profiles
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════


async def _next_turn(session: AsyncSession, session_id: int) -> int:
    """Get the next turn number for a session."""
    result = await session.execute(
        select(func.max(CollegialExchange.turn_number)).where(
            CollegialExchange.session_id == session_id
        )
    )
    max_turn = result.scalar() or 0
    return max_turn + 1


def _parse_json(response: str) -> dict:
    """Parse JSON from an LLM response, tolerating surrounding text."""
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse collegial review JSON")
        return {}
