"""Layer 3: Method Review by Non-Claude Model

CRITICAL: This layer MUST use a non-Claude model (GPT-4o or Gemini).
Uses family-specific rubric for evaluation.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.review import Review
from app.services.llm.router import get_provider_for_model
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model selection: NEVER Claude. Prefer GPT-4o, fall back to Gemini.
# ---------------------------------------------------------------------------
METHOD_MODEL = "gpt-4o"

# ---------------------------------------------------------------------------
# Protocol-specific review prompts
# ---------------------------------------------------------------------------

PROTOCOL_PROMPTS: dict[str, str] = {
    "empirical_causal": """You are an expert reviewer specializing in causal inference methods for governance research.

Review this paper against the following criteria:
1. IDENTIFICATION (weight: 0.30): Is the causal identification strategy credible? Are the assumptions testable?
2. DATA QUALITY (weight: 0.25): Are the data sources appropriate? Is the sample construction transparent?
3. ROBUSTNESS (weight: 0.20): Are falsification tests adequate? Is the result robust to alternative specifications?
4. CAUSAL LANGUAGE (weight: 0.15): Does the paper appropriately limit causal claims to what the design supports?
5. CONTRIBUTION (weight: 0.10): Does this advance knowledge beyond existing literature?

For each criterion, provide:
- Score (1-5)
- Specific issues found
- Required changes (if any)

FATAL FAILURES (instant reject):
{fatal_failures}

MANDATORY CHECKS:
{mandatory_checks}

Return your review as JSON with structure:
{{"criteria": [{{"name": str, "weight": float, "score": int, "issues": [str], "required_changes": [str]}}], "overall_verdict": "pass"|"revision_needed"|"reject", "summary": str, "policy_usefulness": {{"actionability": int, "specificity": int, "evidence_strength": int, "stakeholder_relevance": int, "implementation_feasibility": int}}}}

POLICY-USEFULNESS (score each 1-5 independently):
- actionability: Can a policymaker act on these findings without additional research?
- specificity: Does the paper identify precise institutional mechanisms, not just broad themes?
- evidence_strength: How strong is the evidentiary base for the policy-relevant claims?
- stakeholder_relevance: Are the relevant governance stakeholders clearly identified?
- implementation_feasibility: Are the implied policy changes practically implementable?""",
    "measurement_text": """You are an expert reviewer specializing in text-as-data and measurement methods.

Review this paper against the following criteria:
1. CONSTRUCT VALIDITY (weight: 0.30): Does the measurement capture the intended concept? Are construct boundaries clear?
2. CODING SCHEME (weight: 0.25): Is the coding schema well-defined, exhaustive, and mutually exclusive?
3. INTER-RATER RELIABILITY (weight: 0.20): Are reliability metrics reported and adequate (Cohen's kappa, Krippendorff's alpha)?
4. CORPUS REPRESENTATIVENESS (weight: 0.15): Is the corpus selection justified and potential bias addressed?
5. AGGREGATION (weight: 0.10): Are aggregation rules transparent and defensible?

For each criterion, provide:
- Score (1-5)
- Specific issues found
- Required changes (if any)

FATAL FAILURES (instant reject):
{fatal_failures}

MANDATORY CHECKS:
{mandatory_checks}

Return your review as JSON with structure:
{{"criteria": [{{"name": str, "weight": float, "score": int, "issues": [str], "required_changes": [str]}}], "overall_verdict": "pass"|"revision_needed"|"reject", "summary": str, "policy_usefulness": {{"actionability": int, "specificity": int, "evidence_strength": int, "stakeholder_relevance": int, "implementation_feasibility": int}}}}

POLICY-USEFULNESS (score each 1-5 independently):
- actionability: Can a policymaker act on these findings without additional research?
- specificity: Does the paper identify precise institutional mechanisms, not just broad themes?
- evidence_strength: How strong is the evidentiary base for the policy-relevant claims?
- stakeholder_relevance: Are the relevant governance stakeholders clearly identified?
- implementation_feasibility: Are the implied policy changes practically implementable?""",
    "comparative_historical": """You are an expert reviewer specializing in comparative and historical analysis.

Review this paper against the following criteria:
1. CASE SELECTION (weight: 0.30): Are cases selected to maximize inferential leverage? Is selection bias addressed?
2. RIVAL EXPLANATIONS (weight: 0.25): Are competing explanations systematically considered and tested?
3. TEMPORAL ANALYSIS (weight: 0.20): Are period boundaries justified? Is the timeline internally consistent?
4. SOURCE HIERARCHY (weight: 0.15): Are primary and secondary sources appropriately distinguished and prioritized?
5. GENERALIZABILITY (weight: 0.10): Are scope conditions clearly stated? Is over-generalization avoided?

For each criterion, provide:
- Score (1-5)
- Specific issues found
- Required changes (if any)

FATAL FAILURES (instant reject):
{fatal_failures}

MANDATORY CHECKS:
{mandatory_checks}

Return your review as JSON with structure:
{{"criteria": [{{"name": str, "weight": float, "score": int, "issues": [str], "required_changes": [str]}}], "overall_verdict": "pass"|"revision_needed"|"reject", "summary": str, "policy_usefulness": {{"actionability": int, "specificity": int, "evidence_strength": int, "stakeholder_relevance": int, "implementation_feasibility": int}}}}

POLICY-USEFULNESS (score each 1-5 independently):
- actionability: Can a policymaker act on these findings without additional research?
- specificity: Does the paper identify precise institutional mechanisms, not just broad themes?
- evidence_strength: How strong is the evidentiary base for the policy-relevant claims?
- stakeholder_relevance: Are the relevant governance stakeholders clearly identified?
- implementation_feasibility: Are the implied policy changes practically implementable?""",
    "doctrinal": """You are an expert reviewer specializing in doctrinal legal analysis.

Review this paper against the following criteria:
1. SOURCE HIERARCHY (weight: 0.30): Are legal sources properly ranked (statutes > case law > commentary)?
2. CONTRARY AUTHORITIES (weight: 0.25): Are opposing authorities and dissenting views acknowledged and addressed?
3. JURISDICTIONAL SCOPE (weight: 0.20): Is the jurisdictional scope clearly defined and consistently maintained?
4. INTERPRETIVE FRAMEWORK (weight: 0.15): Is the interpretive framework (textualist, purposive, etc.) explicit and consistently applied?
5. DOCTRINAL CONTRIBUTION (weight: 0.10): Does this advance doctrinal understanding beyond current scholarship?

For each criterion, provide:
- Score (1-5)
- Specific issues found
- Required changes (if any)

FATAL FAILURES (instant reject):
{fatal_failures}

MANDATORY CHECKS:
{mandatory_checks}

Return your review as JSON with structure:
{{"criteria": [{{"name": str, "weight": float, "score": int, "issues": [str], "required_changes": [str]}}], "overall_verdict": "pass"|"revision_needed"|"reject", "summary": str, "policy_usefulness": {{"actionability": int, "specificity": int, "evidence_strength": int, "stakeholder_relevance": int, "implementation_feasibility": int}}}}

POLICY-USEFULNESS (score each 1-5 independently):
- actionability: Can a policymaker act on these findings without additional research?
- specificity: Does the paper identify precise institutional mechanisms, not just broad themes?
- evidence_strength: How strong is the evidentiary base for the policy-relevant claims?
- stakeholder_relevance: Are the relevant governance stakeholders clearly identified?
- implementation_feasibility: Are the implied policy changes practically implementable?""",
    "process_tracing": """You are an expert reviewer specializing in process tracing methodology.

Review this paper against the following criteria:
1. MECHANISM SPECIFICATION (weight: 0.30): Is the causal mechanism precisely specified with observable implications?
2. DIAGNOSTIC TESTS (weight: 0.25): Are hoop tests, smoking gun tests, and doubly decisive tests appropriately deployed?
3. TRIANGULATION (weight: 0.20): Does evidence come from multiple independent sources?
4. ALTERNATIVE MECHANISMS (weight: 0.15): Are rival causal mechanisms systematically tested?
5. CASE JUSTIFICATION (weight: 0.10): Is the case selection justified for theory testing/building?

For each criterion, provide:
- Score (1-5)
- Specific issues found
- Required changes (if any)

FATAL FAILURES (instant reject):
{fatal_failures}

MANDATORY CHECKS:
{mandatory_checks}

Return your review as JSON with structure:
{{"criteria": [{{"name": str, "weight": float, "score": int, "issues": [str], "required_changes": [str]}}], "overall_verdict": "pass"|"revision_needed"|"reject", "summary": str, "policy_usefulness": {{"actionability": int, "specificity": int, "evidence_strength": int, "stakeholder_relevance": int, "implementation_feasibility": int}}}}

POLICY-USEFULNESS (score each 1-5 independently):
- actionability: Can a policymaker act on these findings without additional research?
- specificity: Does the paper identify precise institutional mechanisms, not just broad themes?
- evidence_strength: How strong is the evidentiary base for the policy-relevant claims?
- stakeholder_relevance: Are the relevant governance stakeholders clearly identified?
- implementation_feasibility: Are the implied policy changes practically implementable?""",
    "theory": """You are an expert reviewer specializing in formal theoretical models.

Review this paper against the following criteria:
1. FORMAL PROOF (weight: 0.30): Are proofs correct, complete, and rigorous? Are all steps justified?
2. ASSUMPTIONS (weight: 0.25): Are assumptions clearly stated, economically motivated, and necessary?
3. COMPARATIVE STATICS (weight: 0.20): Are comparative statics derived and economically interpreted?
4. INSTITUTION MAPPING (weight: 0.15): Does the model map to real institutional features?
5. NOVELTY (weight: 0.10): Does the theoretical contribution go beyond existing models?

For each criterion, provide:
- Score (1-5)
- Specific issues found
- Required changes (if any)

FATAL FAILURES (instant reject):
{fatal_failures}

MANDATORY CHECKS:
{mandatory_checks}

Return your review as JSON with structure:
{{"criteria": [{{"name": str, "weight": float, "score": int, "issues": [str], "required_changes": [str]}}], "overall_verdict": "pass"|"revision_needed"|"reject", "summary": str, "policy_usefulness": {{"actionability": int, "specificity": int, "evidence_strength": int, "stakeholder_relevance": int, "implementation_feasibility": int}}}}

POLICY-USEFULNESS (score each 1-5 independently):
- actionability: Can a policymaker act on these findings without additional research?
- specificity: Does the paper identify precise institutional mechanisms, not just broad themes?
- evidence_strength: How strong is the evidentiary base for the policy-relevant claims?
- stakeholder_relevance: Are the relevant governance stakeholders clearly identified?
- implementation_feasibility: Are the implied policy changes practically implementable?""",
    "synthesis_bibliometric": """You are an expert reviewer specializing in systematic reviews and bibliometric analysis.

Review this paper against the following criteria:
1. SEARCH PROTOCOL (weight: 0.30): Is the search strategy comprehensive, reproducible, and documented (PRISMA)?
2. SCREENING CRITERIA (weight: 0.25): Are inclusion/exclusion criteria explicit, justified, and consistently applied?
3. CODING RELIABILITY (weight: 0.20): Is the extraction coding scheme reliable? Are inter-coder metrics reported?
4. SYNTHESIS METHOD (weight: 0.15): Is the synthesis approach (meta-analysis, narrative, vote-counting) appropriate?
5. PUBLICATION BIAS (weight: 0.10): Is publication bias assessed (funnel plots, trim-and-fill, etc.)?

For each criterion, provide:
- Score (1-5)
- Specific issues found
- Required changes (if any)

FATAL FAILURES (instant reject):
{fatal_failures}

MANDATORY CHECKS:
{mandatory_checks}

Return your review as JSON with structure:
{{"criteria": [{{"name": str, "weight": float, "score": int, "issues": [str], "required_changes": [str]}}], "overall_verdict": "pass"|"revision_needed"|"reject", "summary": str, "policy_usefulness": {{"actionability": int, "specificity": int, "evidence_strength": int, "stakeholder_relevance": int, "implementation_feasibility": int}}}}

POLICY-USEFULNESS (score each 1-5 independently):
- actionability: Can a policymaker act on these findings without additional research?
- specificity: Does the paper identify precise institutional mechanisms, not just broad themes?
- evidence_strength: How strong is the evidentiary base for the policy-relevant claims?
- stakeholder_relevance: Are the relevant governance stakeholders clearly identified?
- implementation_feasibility: Are the implied policy changes practically implementable?""",
}

# Default fallback prompt for unknown protocol types.
DEFAULT_PROMPT = """You are an expert academic peer reviewer.

Review this paper against standard methodological criteria:
1. METHODOLOGY (weight: 0.30): Is the method sound and appropriate for the research question?
2. EVIDENCE (weight: 0.25): Is the evidence sufficient and properly analysed?
3. ARGUMENTATION (weight: 0.20): Is the logical structure coherent and compelling?
4. LITERATURE (weight: 0.15): Is the relevant literature properly engaged?
5. CONTRIBUTION (weight: 0.10): Does this advance knowledge in the field?

For each criterion, provide:
- Score (1-5)
- Specific issues found
- Required changes (if any)

FATAL FAILURES (instant reject):
{fatal_failures}

MANDATORY CHECKS:
{mandatory_checks}

Return your review as JSON with structure:
{{"criteria": [{{"name": str, "weight": float, "score": int, "issues": [str], "required_changes": [str]}}], "overall_verdict": "pass"|"revision_needed"|"reject", "summary": str, "policy_usefulness": {{"actionability": int, "specificity": int, "evidence_strength": int, "stakeholder_relevance": int, "implementation_feasibility": int}}}}

POLICY-USEFULNESS (score each 1-5 independently):
- actionability: Can a policymaker act on these findings without additional research?
- specificity: Does the paper identify precise institutional mechanisms, not just broad themes?
- evidence_strength: How strong is the evidentiary base for the policy-relevant claims?
- stakeholder_relevance: Are the relevant governance stakeholders clearly identified?
- implementation_feasibility: Are the implied policy changes practically implementable?"""


async def run_method_review(session: AsyncSession, paper_id: str) -> Review:
    """Run Layer 3 method review using a NON-CLAUDE model.

    1. Load family-specific review_rubric from PaperFamily
    2. Load the manuscript content
    3. Load the lock artifact (for method specification)
    4. Build a review prompt specific to the lock protocol type
    5. Send to GPT-4o (NEVER Claude) via OpenAI provider
    6. Parse structured response with scores per rubric dimension
    7. Apply family-specific weights to compute overall score

    Returns Review with stage='l3_method', model_used must be 'gpt-4o' or similar.
    """
    # ------------------------------------------------------------------
    # 1. Load paper and family
    # ------------------------------------------------------------------
    paper = await _load_paper(session, paper_id)
    if paper is None:
        return await _create_review(
            session,
            paper_id=paper_id,
            family_id=None,
            verdict="fail",
            severity="critical",
            issues=[
                {
                    "check": "paper_exists",
                    "severity": "critical",
                    "message": f"Paper '{paper_id}' not found.",
                }
            ],
            content="Method review aborted: paper not found.",
            model_used=METHOD_MODEL,
            scores={},
        )

    family = await _load_family(session, paper.family_id) if paper.family_id else None

    # Determine protocol type and load family-specific configs.
    protocol_type = family.lock_protocol_type if family else "unknown"
    fatal_failures = _parse_json_field(family.fatal_failures) if family else "None specified"
    mandatory_checks = _parse_json_field(family.mandatory_checks) if family else "None specified"
    review_rubric = safe_json_loads(family.review_rubric, None) if family else None

    # ------------------------------------------------------------------
    # 2. Load manuscript content
    # ------------------------------------------------------------------
    manuscript = await _load_manuscript(paper)
    if not manuscript:
        return await _create_review(
            session,
            paper_id=paper_id,
            family_id=paper.family_id,
            verdict="fail",
            severity="critical",
            issues=[
                {
                    "check": "manuscript_missing",
                    "severity": "critical",
                    "message": "No manuscript content available for review.",
                }
            ],
            content="Method review aborted: no manuscript content.",
            model_used=METHOD_MODEL,
            scores={},
        )

    # ------------------------------------------------------------------
    # 3. Load lock artifact
    # ------------------------------------------------------------------
    lock_content = await _load_lock_yaml(session, paper_id)

    # ------------------------------------------------------------------
    # 4. Build protocol-specific prompt
    # ------------------------------------------------------------------
    prompt_template = PROTOCOL_PROMPTS.get(protocol_type, DEFAULT_PROMPT)

    # Format fatal failures and mandatory checks into the prompt.
    fatal_str = (
        "\n".join(f"- {f}" for f in fatal_failures)
        if isinstance(fatal_failures, list)
        else str(fatal_failures)
    )
    mandatory_str = (
        "\n".join(f"- {c}" for c in mandatory_checks)
        if isinstance(mandatory_checks, list)
        else str(mandatory_checks)
    )

    review_prompt = prompt_template.format(
        fatal_failures=fatal_str,
        mandatory_checks=mandatory_str,
    )

    # Compose the full message with manuscript and lock context.
    user_message = _build_user_message(
        review_prompt=review_prompt,
        manuscript=manuscript,
        lock_content=lock_content,
        protocol_type=protocol_type,
    )

    # ------------------------------------------------------------------
    # 5. Send to GPT-4o (NEVER Claude)
    # ------------------------------------------------------------------
    provider = get_provider_for_model(METHOD_MODEL)

    try:
        response = await provider.complete(
            messages=[{"role": "user", "content": user_message}],
            model=METHOD_MODEL,
            temperature=0.3,
            max_tokens=4096,
        )
    except Exception as exc:
        logger.error("[%s] L3 method review LLM call failed: %s", paper_id, exc)
        return await _create_review(
            session,
            paper_id=paper_id,
            family_id=paper.family_id,
            verdict="fail",
            severity="critical",
            issues=[
                {"check": "llm_error", "severity": "critical", "message": f"LLM call failed: {exc}"}
            ],
            content=f"Method review aborted: LLM error ({exc})",
            model_used=METHOD_MODEL,
            scores={},
        )

    # ------------------------------------------------------------------
    # 6. Parse structured response
    # ------------------------------------------------------------------
    parsed = _parse_review_response(response)
    issues: list[dict] = []
    scores: dict[str, Any] = {}
    policy_usefulness: dict | None = None

    if parsed is None:
        # Could not parse JSON -- treat the raw response as a text review.
        issues.append(
            {
                "check": "response_parse_error",
                "severity": "warning",
                "message": "Could not parse structured JSON from model response.",
            }
        )
        # Attempt to extract verdict from text.
        verdict = _extract_text_verdict(response)
    else:
        # Extract per-criterion issues and scores.
        criteria = parsed.get("criteria", [])
        for criterion in criteria:
            name = criterion.get("name", "unknown")
            score = criterion.get("score", 0)
            weight = criterion.get("weight", 0.0)
            criterion_issues = criterion.get("issues", [])
            required_changes = criterion.get("required_changes", [])

            scores[name] = {"score": score, "weight": weight}

            for issue_text in criterion_issues:
                issues.append(
                    {
                        "check": f"method_{name.lower().replace(' ', '_')}",
                        "severity": "warning" if score >= 3 else "critical",
                        "message": issue_text,
                        "criterion": name,
                        "score": score,
                    }
                )

            for change in required_changes:
                issues.append(
                    {
                        "check": f"required_change_{name.lower().replace(' ', '_')}",
                        "severity": "critical",
                        "message": f"Required change ({name}): {change}",
                        "criterion": name,
                    }
                )

        # ------------------------------------------------------------------
        # 7. Apply weights to compute overall score
        # ------------------------------------------------------------------
        verdict = parsed.get("overall_verdict", "revision_needed")

        # If family has custom rubric weights, apply them.
        if review_rubric and "weights" in review_rubric:
            custom_weights = review_rubric["weights"]
            for criterion in criteria:
                name = criterion.get("name", "")
                if name in custom_weights:
                    criterion["weight"] = custom_weights[name]
                    scores[name]["weight"] = custom_weights[name]

        weighted_score = _compute_weighted_score(criteria)
        scores["_weighted_total"] = round(weighted_score, 2)

        # Extract policy-usefulness scores if present
        policy_usefulness = parsed.get("policy_usefulness")

        # Override verdict based on weighted score if needed.
        if weighted_score < 2.0:
            verdict = "reject"
        elif weighted_score < 3.0 and verdict == "pass":
            verdict = "revision_needed"

    # Normalize verdict to our schema.
    if verdict == "reject":
        verdict = "fail"
    elif verdict not in ("pass", "fail", "revision_needed"):
        verdict = "revision_needed"

    # Determine severity from verdict.
    critical_count = sum(1 for i in issues if i.get("severity") == "critical")
    if verdict == "fail":
        max_severity = "critical"
    elif critical_count > 0:
        max_severity = "warning"
    else:
        max_severity = "info"

    # Build summary.
    summary = parsed.get("summary", response[:1000]) if parsed else response[:1000]
    summary_text = (
        f"Method review ({protocol_type}) completed by {METHOD_MODEL}.\n"
        f"Verdict: {verdict}\n"
        f"Weighted score: {scores.get('_weighted_total', 'N/A')}\n"
        f"Issues found: {len(issues)}\n\n"
        f"Summary: {summary}"
    )

    return await _create_review(
        session,
        paper_id=paper_id,
        family_id=paper.family_id,
        verdict=verdict,
        severity=max_severity,
        issues=issues,
        content=summary_text,
        model_used=METHOD_MODEL,
        scores=scores,
        policy_scores=policy_usefulness,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper | None:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_family(session: AsyncSession, family_id: str | None) -> PaperFamily | None:
    if family_id is None:
        return None
    stmt = select(PaperFamily).where(PaperFamily.id == family_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_manuscript(paper: Paper) -> str | None:
    """Load manuscript text from TeX file, metadata, or abstract."""
    tex_path = paper.paper_tex_path
    if tex_path:
        try:
            import aiofiles

            async with aiofiles.open(tex_path) as f:
                return await f.read()
        except (FileNotFoundError, ImportError):
            pass

    meta = safe_json_loads(paper.metadata_json, {})
    if "manuscript_text" in meta:
        return meta["manuscript_text"]

    return paper.abstract


async def _load_lock_yaml(session: AsyncSession, paper_id: str) -> str | None:
    """Load the active lock artifact YAML."""
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


def _parse_json_field(field: str | None) -> list[str] | str:
    """Parse a JSON field that should be a list of strings."""
    if not field:
        return "None specified"
    try:
        parsed = json.loads(field)
        if isinstance(parsed, list):
            return parsed
        return str(parsed)
    except (json.JSONDecodeError, TypeError):
        return field


def _build_user_message(
    *,
    review_prompt: str,
    manuscript: str,
    lock_content: str | None,
    protocol_type: str,
) -> str:
    """Assemble the full user message for the method review LLM call."""
    parts = [review_prompt]

    if lock_content:
        parts.append(
            f"\n\n--- LOCK ARTIFACT (Protocol: {protocol_type}) ---\n{lock_content[:3000]}"
        )

    # Truncate manuscript to fit within token limits (roughly 12k chars ~3k tokens).
    max_manuscript_chars = 12000
    if len(manuscript) > max_manuscript_chars:
        parts.append(
            f"\n\n--- MANUSCRIPT (truncated to {max_manuscript_chars} chars) ---\n"
            f"{manuscript[:max_manuscript_chars]}\n[... truncated ...]"
        )
    else:
        parts.append(f"\n\n--- MANUSCRIPT ---\n{manuscript}")

    return "\n".join(parts)


def _parse_review_response(response: str) -> dict | None:
    """Try to parse the model response as JSON.

    The response may contain markdown code fences or other text around the JSON.
    """
    # Try direct parse first.
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to extract JSON from code fences.
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    # Try to find JSON object in the response.
    brace_start = response.find("{")
    brace_end = response.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(response[brace_start : brace_end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _extract_text_verdict(response: str) -> str:
    """Extract a verdict from unstructured text response."""
    upper = response.upper()
    if "REJECT" in upper[-500:]:
        return "fail"
    if "PASS" in upper[-500:] and "REVISION" not in upper[-500:]:
        return "pass"
    return "revision_needed"


def _compute_weighted_score(criteria: list[dict]) -> float:
    """Compute weighted average score from criteria list."""
    total_weight = 0.0
    weighted_sum = 0.0

    for criterion in criteria:
        weight = criterion.get("weight", 0.0)
        score = criterion.get("score", 0)
        if isinstance(weight, (int, float)) and isinstance(score, (int, float)):
            weighted_sum += weight * score
            total_weight += weight

    if total_weight == 0:
        return 0.0
    return weighted_sum / total_weight


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
    scores: dict,
    policy_scores: dict | None = None,
) -> Review:
    """Create and persist a Layer 3 Review record."""
    # Embed scores into issues_json alongside the issues list.
    issues_payload = {
        "issues": issues,
        "scores": scores,
    }
    review = Review(
        paper_id=paper_id,
        stage="l3_method",
        model_used=model_used,
        verdict=verdict,
        content=content,
        severity=severity,
        resolution_status="open" if verdict != "pass" else "resolved",
        family_id=family_id,
        review_rubric_version="method_v1",
        issues_json=json.dumps(issues_payload),
    )
    if policy_scores:
        review.policy_scores_json = json.dumps(policy_scores)
    session.add(review)
    await session.flush()
    logger.info(
        "[%s] L3 method review (%s): verdict=%s, issues=%d, model=%s",
        paper_id,
        family_id or "no-family",
        verdict,
        len(issues),
        model_used,
    )
    return review
