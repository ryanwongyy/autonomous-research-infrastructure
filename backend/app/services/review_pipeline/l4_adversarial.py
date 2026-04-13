"""Layer 4: Adversarial Red-Team Review

Job: try to KILL the paper if it should die.
Finds alternative explanations, hidden confounding, benchmark contamination,
doctrinal omissions, unsupported causal language, duplicates, fragile sources.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_map import ClaimMap
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.review import Review
from app.models.source_card import SourceCard
from app.services.llm.router import get_provider_for_model
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Adversarial model assignments
# ---------------------------------------------------------------------------
ADVERSARIAL_CLAUDE_MODEL = "claude-sonnet-4-6"
ADVERSARIAL_GPT_MODEL = "gpt-4o"

# ---------------------------------------------------------------------------
# Adversarial prompt templates
# ---------------------------------------------------------------------------

ALTERNATIVE_EXPLANATION_PROMPT = """You are a hostile but fair academic reviewer. Your job is to find ALTERNATIVE EXPLANATIONS for the paper's results.

For each central claim, identify:
1. What alternative causal mechanisms could produce the same observed patterns?
2. What confounders are unaddressed or under-addressed?
3. Could reverse causality explain the findings?
4. Could selection effects drive the results?
5. Are there measurement artifacts that could generate spurious results?

PAPER CONTENT:
{manuscript}

{lock_context}

{claim_context}

For each alternative explanation, rate its plausibility (low/medium/high) and whether the paper addresses it.

Return JSON:
{{"alternatives": [{{"claim": str, "alternative": str, "plausibility": "low"|"medium"|"high", "addressed_in_paper": bool, "recommendation": str}}], "overall_threat": "low"|"medium"|"high"|"fatal", "verdict": "pass"|"revision_needed"|"reject"}}"""

SOURCE_FRAGILITY_PROMPT = """You are a data integrity specialist reviewing the fragility of a paper's evidence base.

Your task: stress-test every data source and empirical claim.

For each source or data-dependent claim:
1. What would happen if the source data changed by 10%? Would the conclusion hold?
2. Is there a single data point or source driving the result?
3. Are any sources known to have revision histories, retracted data, or quality issues?
4. Could the data collection methodology introduce systematic bias?
5. Is there a closer, more recent paper or dataset that makes this analysis redundant?

PAPER CONTENT:
{manuscript}

{source_context}

{claim_context}

For each fragility concern, rate severity (info/warning/critical).

Return JSON:
{{"fragility_findings": [{{"source_or_claim": str, "concern": str, "severity": "info"|"warning"|"critical", "recommendation": str}}], "redundancy_risk": str, "overall_fragility": "low"|"medium"|"high"|"fatal", "verdict": "pass"|"revision_needed"|"reject"}}"""

CAUSAL_LANGUAGE_PROMPT = """You are a methodologist specializing in causal inference. Your task is to find EVERY instance of unsupported causal language in this paper.

Specifically identify:
1. Causal claims ("X causes Y", "X leads to Y", "X increases Y") not supported by the research design
2. Implied causation through language choice ("impact", "effect", "due to") without a credible identification strategy
3. Over-generalization beyond the sample or context studied
4. Language that implies mechanisms not tested in the paper
5. What would a hostile reviewer at a top-5 economics journal attack first?

PAPER CONTENT:
{manuscript}

{lock_context}

For each finding, provide the exact text and the issue.

Return JSON:
{{"language_issues": [{{"text": str, "issue": str, "severity": "info"|"warning"|"critical", "suggested_fix": str}}], "design_mismatch_count": int, "verdict": "pass"|"revision_needed"|"reject"}}"""


async def run_adversarial_review(
    session: AsyncSession, paper_id: str
) -> Review:
    """Run Layer 4 adversarial red-team review.

    1. Load manuscript, lock artifact, claim map, source manifest
    2. Run MULTIPLE adversarial prompts in parallel:
       a. Alternative explanation hunter (Claude)
       b. Source fragility attacker (GPT-4o)
       c. Causal language checker (Claude)
    3. Each adversarial prompt tries to break the paper
    4. Aggregate findings. If any adversarial model returns 'reject', the paper fails.

    Returns Review with stage='l4_adversarial'.
    Uses multiple models via asyncio.gather for parallel adversarial checks.
    """
    # ------------------------------------------------------------------
    # Load all context
    # ------------------------------------------------------------------
    paper = await _load_paper(session, paper_id)
    if paper is None:
        return await _create_review(
            session,
            paper_id=paper_id,
            family_id=None,
            verdict="fail",
            severity="critical",
            issues=[{"check": "paper_exists", "severity": "critical",
                     "message": f"Paper '{paper_id}' not found."}],
            content="Adversarial review aborted: paper not found.",
            model_used="multi-model",
            sub_reviews={},
        )

    manuscript = await _load_manuscript(paper)
    if not manuscript:
        return await _create_review(
            session,
            paper_id=paper_id,
            family_id=paper.family_id,
            verdict="fail",
            severity="critical",
            issues=[{"check": "manuscript_missing", "severity": "critical",
                     "message": "No manuscript content for adversarial review."}],
            content="Adversarial review aborted: no manuscript content.",
            model_used="multi-model",
            sub_reviews={},
        )

    lock_content = await _load_lock_yaml(session, paper_id)
    claims = await _load_claims(session, paper_id)
    source_cards = await _load_source_cards(session, paper_id, claims)

    # Build context strings for prompts.
    lock_context = (
        f"LOCK ARTIFACT:\n{lock_content[:2000]}" if lock_content else "No lock artifact available."
    )
    claim_context = _build_claim_context(claims)
    source_context = _build_source_context(source_cards)

    # Truncate manuscript for token limits.
    max_chars = 10000
    manuscript_truncated = manuscript[:max_chars]
    if len(manuscript) > max_chars:
        manuscript_truncated += "\n[... truncated ...]"

    # ------------------------------------------------------------------
    # Run adversarial checks in parallel
    # ------------------------------------------------------------------
    tasks = [
        _run_alternative_explanation_check(
            manuscript=manuscript_truncated,
            lock_context=lock_context,
            claim_context=claim_context,
        ),
        _run_source_fragility_check(
            manuscript=manuscript_truncated,
            source_context=source_context,
            claim_context=claim_context,
        ),
        _run_causal_language_check(
            manuscript=manuscript_truncated,
            lock_context=lock_context,
        ),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Aggregate findings
    # ------------------------------------------------------------------
    all_issues: list[dict] = []
    sub_reviews: dict[str, Any] = {}
    any_reject = False

    check_names = ["alternative_explanation", "source_fragility", "causal_language"]
    check_models = [ADVERSARIAL_CLAUDE_MODEL, ADVERSARIAL_GPT_MODEL, ADVERSARIAL_CLAUDE_MODEL]

    for i, (name, model_name) in enumerate(zip(check_names, check_models)):
        result = results[i]

        if isinstance(result, Exception):
            logger.error(
                "[%s] Adversarial check '%s' failed: %s", paper_id, name, result
            )
            all_issues.append({
                "check": f"adversarial_{name}_error",
                "severity": "warning",
                "message": f"Adversarial check '{name}' ({model_name}) failed: {result}",
            })
            sub_reviews[name] = {"error": str(result), "model": model_name}
            continue

        parsed, raw_response = result
        sub_reviews[name] = {
            "model": model_name,
            "parsed": parsed is not None,
            "raw_length": len(raw_response),
        }

        if parsed is None:
            all_issues.append({
                "check": f"adversarial_{name}_parse_error",
                "severity": "warning",
                "message": (
                    f"Could not parse structured response from {name} check ({model_name})."
                ),
            })
            # Try to extract verdict from text.
            if "REJECT" in raw_response.upper()[-500:]:
                any_reject = True
            continue

        # Extract check-specific findings.
        check_issues = _extract_issues_from_parsed(name, parsed)
        all_issues.extend(check_issues)

        # Check verdict from this adversarial check.
        check_verdict = parsed.get("verdict", "revision_needed")
        sub_reviews[name]["verdict"] = check_verdict

        if check_verdict == "reject":
            any_reject = True

    # ------------------------------------------------------------------
    # Determine final verdict
    # ------------------------------------------------------------------
    critical_count = sum(1 for i in all_issues if i.get("severity") == "critical")

    if any_reject:
        verdict = "fail"
        max_severity = "critical"
    elif critical_count > 0:
        verdict = "revision_needed"
        max_severity = "critical"
    elif all_issues:
        verdict = "revision_needed"
        max_severity = "warning"
    else:
        verdict = "pass"
        max_severity = "info"

    # Build summary.
    summary_parts = [
        "Adversarial red-team review completed.",
        f"Checks run: {', '.join(check_names)}",
        f"Models used: Claude ({ADVERSARIAL_CLAUDE_MODEL}), GPT-4o ({ADVERSARIAL_GPT_MODEL})",
        f"Total findings: {len(all_issues)}",
        f"Critical: {critical_count}",
        f"Any reject: {any_reject}",
        f"Final verdict: {verdict}",
    ]
    # Add top-level summaries from each check.
    for name in check_names:
        info = sub_reviews.get(name, {})
        v = info.get("verdict", "error")
        summary_parts.append(f"  {name}: {v} (model: {info.get('model', '?')})")

    return await _create_review(
        session,
        paper_id=paper_id,
        family_id=paper.family_id,
        verdict=verdict,
        severity=max_severity,
        issues=all_issues,
        content="\n".join(summary_parts),
        model_used=f"{ADVERSARIAL_CLAUDE_MODEL},{ADVERSARIAL_GPT_MODEL}",
        sub_reviews=sub_reviews,
    )


# ---------------------------------------------------------------------------
# Individual adversarial checks
# ---------------------------------------------------------------------------


async def _run_alternative_explanation_check(
    *, manuscript: str, lock_context: str, claim_context: str
) -> tuple[dict | None, str]:
    """Run the alternative explanation adversarial check using Claude."""
    prompt = ALTERNATIVE_EXPLANATION_PROMPT.format(
        manuscript=manuscript,
        lock_context=lock_context,
        claim_context=claim_context,
    )

    provider = get_provider_for_model(ADVERSARIAL_CLAUDE_MODEL)
    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=ADVERSARIAL_CLAUDE_MODEL,
        temperature=0.4,
        max_tokens=4096,
    )

    parsed = _parse_json_response(response)
    return parsed, response


async def _run_source_fragility_check(
    *, manuscript: str, source_context: str, claim_context: str
) -> tuple[dict | None, str]:
    """Run the source fragility adversarial check using GPT-4o."""
    prompt = SOURCE_FRAGILITY_PROMPT.format(
        manuscript=manuscript,
        source_context=source_context,
        claim_context=claim_context,
    )

    provider = get_provider_for_model(ADVERSARIAL_GPT_MODEL)
    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=ADVERSARIAL_GPT_MODEL,
        temperature=0.4,
        max_tokens=4096,
    )

    parsed = _parse_json_response(response)
    return parsed, response


async def _run_causal_language_check(
    *, manuscript: str, lock_context: str
) -> tuple[dict | None, str]:
    """Run the causal language adversarial check using Claude."""
    prompt = CAUSAL_LANGUAGE_PROMPT.format(
        manuscript=manuscript,
        lock_context=lock_context,
    )

    provider = get_provider_for_model(ADVERSARIAL_CLAUDE_MODEL)
    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=ADVERSARIAL_CLAUDE_MODEL,
        temperature=0.3,
        max_tokens=4096,
    )

    parsed = _parse_json_response(response)
    return parsed, response


# ---------------------------------------------------------------------------
# Issue extraction from parsed results
# ---------------------------------------------------------------------------


def _extract_issues_from_parsed(check_name: str, parsed: dict) -> list[dict]:
    """Extract standardized issues from a parsed adversarial check response."""
    issues: list[dict] = []

    if check_name == "alternative_explanation":
        for alt in parsed.get("alternatives", []):
            plausibility = alt.get("plausibility", "medium")
            addressed = alt.get("addressed_in_paper", False)

            if plausibility == "high" and not addressed:
                severity = "critical"
            elif plausibility == "medium" and not addressed:
                severity = "warning"
            else:
                severity = "info"

            issues.append({
                "check": "adversarial_alternative_explanation",
                "severity": severity,
                "message": (
                    f"Alternative explanation for '{alt.get('claim', '?')[:60]}': "
                    f"{alt.get('alternative', '?')[:120]}"
                ),
                "plausibility": plausibility,
                "addressed": addressed,
                "recommendation": alt.get("recommendation", ""),
            })

        # Check overall threat level.
        threat = parsed.get("overall_threat", "medium")
        if threat == "fatal":
            issues.append({
                "check": "adversarial_fatal_threat",
                "severity": "critical",
                "message": "Overall alternative explanation threat rated as FATAL.",
            })

    elif check_name == "source_fragility":
        for finding in parsed.get("fragility_findings", []):
            severity = finding.get("severity", "warning")
            issues.append({
                "check": "adversarial_source_fragility",
                "severity": severity,
                "message": (
                    f"Fragility in '{finding.get('source_or_claim', '?')[:60]}': "
                    f"{finding.get('concern', '?')[:120]}"
                ),
                "recommendation": finding.get("recommendation", ""),
            })

        # Check redundancy risk.
        redundancy = parsed.get("redundancy_risk", "")
        if redundancy:
            issues.append({
                "check": "adversarial_redundancy",
                "severity": "warning",
                "message": f"Redundancy risk: {redundancy[:200]}",
            })

        fragility_level = parsed.get("overall_fragility", "medium")
        if fragility_level == "fatal":
            issues.append({
                "check": "adversarial_fatal_fragility",
                "severity": "critical",
                "message": "Overall source fragility rated as FATAL.",
            })

    elif check_name == "causal_language":
        for lang_issue in parsed.get("language_issues", []):
            severity = lang_issue.get("severity", "warning")
            issues.append({
                "check": "adversarial_causal_language",
                "severity": severity,
                "message": (
                    f"Causal language issue: '{lang_issue.get('text', '?')[:60]}' -- "
                    f"{lang_issue.get('issue', '?')[:120]}"
                ),
                "suggested_fix": lang_issue.get("suggested_fix", ""),
            })

        mismatch_count = parsed.get("design_mismatch_count", 0)
        if mismatch_count > 3:
            issues.append({
                "check": "adversarial_design_mismatch",
                "severity": "critical",
                "message": (
                    f"{mismatch_count} design-language mismatches found. "
                    f"Paper claims more than the research design supports."
                ),
            })

    return issues


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------


def _build_claim_context(claims: list[ClaimMap]) -> str:
    """Build a summary of claims for inclusion in adversarial prompts."""
    if not claims:
        return "No claim map entries available."

    lines = ["CLAIM MAP:"]
    for claim in claims[:20]:  # Cap at 20 to control token usage.
        src = claim.source_card_id or "result-object"
        status = claim.verification_status
        lines.append(
            f"  - [{claim.claim_type}] {claim.claim_text[:100]} "
            f"(source: {src}, status: {status})"
        )

    if len(claims) > 20:
        lines.append(f"  ... and {len(claims) - 20} more claims")

    return "\n".join(lines)


def _build_source_context(source_cards: dict[str, SourceCard]) -> str:
    """Build a summary of source cards for the fragility check."""
    if not source_cards:
        return "No source card information available."

    lines = ["SOURCE CARDS:"]
    for sc_id, sc in source_cards.items():
        lines.append(
            f"  - {sc.name} (Tier {sc.tier}, type: {sc.source_type}, "
            f"fragility: {sc.fragility_score:.2f})"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper | None:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_manuscript(paper: Paper) -> str | None:
    tex_path = paper.paper_tex_path
    if tex_path:
        try:
            import aiofiles
            async with aiofiles.open(tex_path, "r") as f:
                return await f.read()
        except (FileNotFoundError, ImportError):
            pass

    meta = safe_json_loads(paper.metadata_json, {})
    if "manuscript_text" in meta:
        return meta["manuscript_text"]

    return paper.abstract


async def _load_lock_yaml(session: AsyncSession, paper_id: str) -> str | None:
    stmt = (
        select(LockArtifact)
        .where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    lock = result.scalar_one_or_none()
    return lock.lock_yaml if lock else None


async def _load_claims(session: AsyncSession, paper_id: str) -> list[ClaimMap]:
    stmt = select(ClaimMap).where(ClaimMap.paper_id == paper_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _load_source_cards(
    session: AsyncSession, paper_id: str, claims: list[ClaimMap]
) -> dict[str, SourceCard]:
    """Load all unique source cards referenced by the paper's claims."""
    card_ids = {c.source_card_id for c in claims if c.source_card_id}
    if not card_ids:
        return {}

    stmt = select(SourceCard).where(SourceCard.id.in_(card_ids))
    result = await session.execute(stmt)
    cards = result.scalars().all()
    return {c.id: c for c in cards}


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_json_response(response: str) -> dict | None:
    """Try to parse JSON from a model response."""
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    brace_start = response.find("{")
    brace_end = response.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(response[brace_start:brace_end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    return None


# ---------------------------------------------------------------------------
# Review persistence
# ---------------------------------------------------------------------------


async def _create_review(
    session: AsyncSession,
    *,
    paper_id: str,
    family_id: str | None,
    verdict: str,
    severity: str,
    issues: list[dict],
    content: str,
    model_used: str,
    sub_reviews: dict,
) -> Review:
    """Create and persist a Layer 4 Review record."""
    issues_payload = {
        "issues": issues,
        "sub_reviews": sub_reviews,
    }
    review = Review(
        paper_id=paper_id,
        stage="l4_adversarial",
        model_used=model_used,
        verdict=verdict,
        content=content,
        severity=severity,
        resolution_status="open" if verdict != "pass" else "resolved",
        family_id=family_id,
        review_rubric_version="adversarial_v1",
        issues_json=json.dumps(issues_payload),
    )
    session.add(review)
    await session.flush()
    logger.info(
        "[%s] L4 adversarial review: verdict=%s, issues=%d, models=%s",
        paper_id, verdict, len(issues), model_used,
    )
    return review
