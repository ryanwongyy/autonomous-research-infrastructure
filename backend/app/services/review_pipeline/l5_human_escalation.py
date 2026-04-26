"""Layer 5: Human Escalation

No model call. Generates structured report for human review.
Triggers when: reviewers differ by >1 grade, legal uncertainty,
or paper is benchmark-strong but potentially misleading.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.review import Review
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Verdict grade mapping for disagreement detection
# ---------------------------------------------------------------------------
VERDICT_GRADES: dict[str, int] = {
    "pass": 3,
    "revision_needed": 2,
    "fail": 1,
}


async def check_escalation_needed(
    session: AsyncSession, paper_id: str
) -> bool:
    """Check if this paper needs human escalation based on review results.

    Escalation triggers:
    1. L3 (method) and L4 (adversarial) verdicts differ by >1 grade
    2. Any critical severity issue is still unresolved (open)
    3. Legal/doctrinal uncertainty flagged in any review
    4. Benchmark-strong paper with misleading indicators
    5. Multiple layers disagree (e.g. L3 says pass, L4 says fail)
    """
    reviews = await _load_reviews(session, paper_id)

    if not reviews:
        return False

    triggers: list[str] = []

    # Index reviews by stage for quick lookup.
    by_stage: dict[str, Review] = {}
    for r in reviews:
        # Keep the latest review per stage.
        if r.stage not in by_stage or r.id > by_stage[r.stage].id:
            by_stage[r.stage] = r

    # ------------------------------------------------------------------
    # Trigger 1: L3/L4 verdict disagreement >1 grade
    # ------------------------------------------------------------------
    l3 = by_stage.get("l3_method")
    l4 = by_stage.get("l4_adversarial")

    if l3 and l4:
        l3_grade = VERDICT_GRADES.get(l3.verdict, 2)
        l4_grade = VERDICT_GRADES.get(l4.verdict, 2)
        grade_diff = abs(l3_grade - l4_grade)

        if grade_diff > 1:
            triggers.append(
                f"L3-L4 grade disagreement: L3={l3.verdict}({l3_grade}), "
                f"L4={l4.verdict}({l4_grade}), diff={grade_diff}"
            )

    # ------------------------------------------------------------------
    # Trigger 2: Unresolved critical issues
    # ------------------------------------------------------------------
    for r in reviews:
        if r.severity == "critical" and r.resolution_status == "open":
            triggers.append(
                f"Unresolved critical issue in {r.stage} "
                f"(review_id={r.id}): {r.content[:100]}"
            )
            break  # One is enough to trigger.

    # ------------------------------------------------------------------
    # Trigger 3: Legal/doctrinal uncertainty
    # ------------------------------------------------------------------
    for r in reviews:
        if r.issues_json:
            issues_data = safe_json_loads(r.issues_json, [])
            issues_list = (
                issues_data.get("issues", issues_data)
                if isinstance(issues_data, dict) else issues_data
            )
            if isinstance(issues_list, list):
                for issue in issues_list:
                    if isinstance(issue, dict):
                        msg = issue.get("message", "").lower()
                        check = issue.get("check", "").lower()
                        if any(
                            kw in msg or kw in check
                            for kw in [
                                "legal", "doctrinal", "jurisdiction",
                                "regulatory", "statute", "constitutional",
                            ]
                        ):
                            triggers.append(
                                f"Legal/doctrinal uncertainty in {r.stage}: "
                                f"{issue.get('message', '')[:100]}"
                            )
                            break

    # ------------------------------------------------------------------
    # Trigger 4: Benchmark-strong but potentially misleading
    # ------------------------------------------------------------------
    paper = await _load_paper(session, paper_id)
    if paper:
        # A paper is "benchmark-strong" if L3 method review passes
        # but L4 adversarial finds critical issues.
        if l3 and l4:
            if l3.verdict == "pass" and l4.severity == "critical":
                triggers.append(
                    "Benchmark-strong but adversarial-critical: L3 passed but "
                    "L4 found critical issues. Potentially misleading results."
                )

        # Check if any adversarial sub-review flagged "fatal" threat.
        if l4 and l4.issues_json:
            l4_data = safe_json_loads(l4.issues_json, {})
            sub_reviews = l4_data.get("sub_reviews", {}) if isinstance(l4_data, dict) else {}
            for name, info in sub_reviews.items():
                if isinstance(info, dict) and info.get("verdict") == "reject":
                    if l3 and l3.verdict in ("pass", "revision_needed"):
                        triggers.append(
                            f"Mixed signal: adversarial {name} says reject "
                            f"but L3 method says {l3.verdict}."
                        )

    # ------------------------------------------------------------------
    # Trigger 5: Multiple layers disagree
    # ------------------------------------------------------------------
    verdicts = {stage: r.verdict for stage, r in by_stage.items()}
    unique_verdicts = set(verdicts.values())
    if len(unique_verdicts) >= 3:
        triggers.append(
            f"Three-way verdict split across layers: {verdicts}"
        )

    if triggers:
        logger.info(
            "[%s] Escalation triggered (%d reasons): %s",
            paper_id, len(triggers), "; ".join(triggers[:3]),
        )

    return len(triggers) > 0


async def generate_escalation_report(
    session: AsyncSession, paper_id: str
) -> Review:
    """Generate a structured escalation report for human review.

    1. Aggregate all L1-L4 review results
    2. Identify escalation triggers
    3. Generate structured escalation report with:
       - Summary of all review findings
       - Specific questions for human reviewer
       - Recommended actions
       - Risk assessment
    4. Create GitHub Issue (placeholder -- logs the intent)
    5. Set Paper.funnel_stage to 'reviewing' with release_status 'internal'

    Returns Review with stage='l5_human', model_used='system'.
    """
    reviews = await _load_reviews(session, paper_id)
    paper = await _load_paper(session, paper_id)

    if not paper:
        return await _create_review(
            session,
            paper_id=paper_id,
            family_id=None,
            verdict="fail",
            severity="critical",
            issues=[{"check": "paper_exists", "severity": "critical",
                     "message": f"Paper '{paper_id}' not found."}],
            content="Escalation report aborted: paper not found.",
        )

    # ------------------------------------------------------------------
    # 1. Aggregate all L1-L4 results
    # ------------------------------------------------------------------
    by_stage: dict[str, Review] = {}
    for r in reviews:
        if r.stage not in by_stage or r.id > by_stage[r.stage].id:
            by_stage[r.stage] = r

    layer_summaries: list[dict] = []
    all_critical_issues: list[dict] = []
    all_warnings: list[dict] = []

    for stage_name in ["l1_structural", "l2_provenance", "l3_method", "l4_adversarial"]:
        review = by_stage.get(stage_name)
        if not review:
            layer_summaries.append({
                "stage": stage_name,
                "verdict": "not_run",
                "severity": "info",
                "issues_count": 0,
                "summary": "Layer not executed.",
            })
            continue

        # Parse issues from the review.
        stage_issues = _extract_issues(review)
        critical = [i for i in stage_issues if i.get("severity") == "critical"]
        warnings = [i for i in stage_issues if i.get("severity") == "warning"]

        layer_summaries.append({
            "stage": stage_name,
            "verdict": review.verdict,
            "severity": review.severity,
            "model_used": review.model_used,
            "issues_count": len(stage_issues),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "summary": review.content[:300],
        })

        all_critical_issues.extend(critical)
        all_warnings.extend(warnings)

    # ------------------------------------------------------------------
    # 2. Identify specific escalation triggers
    # ------------------------------------------------------------------
    escalation_triggers = _identify_triggers(by_stage, paper)

    # ------------------------------------------------------------------
    # 3. Generate structured escalation report
    # ------------------------------------------------------------------
    questions_for_human = _generate_human_questions(
        by_stage, escalation_triggers, all_critical_issues
    )
    recommended_actions = _generate_recommended_actions(
        by_stage, escalation_triggers, all_critical_issues
    )
    risk_assessment = _assess_risk(by_stage, all_critical_issues, all_warnings)

    # Build the full report content.
    report_sections = [
        "=" * 60,
        "HUMAN ESCALATION REPORT",
        f"Paper: {paper.title[:100]}",
        f"Paper ID: {paper_id}",
        f"Family: {paper.family_id or 'N/A'}",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "=" * 60,
        "",
        "--- LAYER SUMMARIES ---",
    ]
    for ls in layer_summaries:
        report_sections.append(
            f"  {ls['stage']}: verdict={ls['verdict']}, "
            f"severity={ls['severity']}, issues={ls['issues_count']}"
        )
        if ls.get("summary"):
            report_sections.append(f"    {ls['summary'][:200]}")

    report_sections.extend([
        "",
        "--- ESCALATION TRIGGERS ---",
    ])
    for trigger in escalation_triggers:
        report_sections.append(f"  * {trigger}")

    report_sections.extend([
        "",
        f"--- CRITICAL ISSUES ({len(all_critical_issues)}) ---",
    ])
    for issue in all_critical_issues[:10]:
        report_sections.append(
            f"  [{issue.get('check', '?')}] {issue.get('message', '')[:150]}"
        )
    if len(all_critical_issues) > 10:
        report_sections.append(f"  ... and {len(all_critical_issues) - 10} more")

    report_sections.extend([
        "",
        "--- QUESTIONS FOR HUMAN REVIEWER ---",
    ])
    for i, question in enumerate(questions_for_human, 1):
        report_sections.append(f"  {i}. {question}")

    report_sections.extend([
        "",
        "--- RECOMMENDED ACTIONS ---",
    ])
    for action in recommended_actions:
        report_sections.append(f"  - {action}")

    report_sections.extend([
        "",
        "--- RISK ASSESSMENT ---",
        f"  Overall risk: {risk_assessment['level']}",
        f"  Confidence: {risk_assessment['confidence']}",
        f"  Rationale: {risk_assessment['rationale']}",
    ])

    report_content = "\n".join(report_sections)

    # ------------------------------------------------------------------
    # 4. Placeholder: log GitHub Issue creation intent
    # ------------------------------------------------------------------
    logger.info(
        "[%s] ESCALATION: Would create GitHub Issue -- '%s' (risk: %s, triggers: %d)",
        paper_id,
        f"Human Review Needed: {paper.title[:60]}",
        risk_assessment["level"],
        len(escalation_triggers),
    )

    # ------------------------------------------------------------------
    # 5. Update Paper funnel_stage and release_status
    # ------------------------------------------------------------------
    await session.execute(
        update(Paper)
        .where(Paper.id == paper_id)
        .values(funnel_stage="reviewing", release_status="internal")
    )

    # Assemble issues for the review record.
    escalation_issues = [
        {
            "check": "escalation_trigger",
            "severity": "critical",
            "message": trigger,
        }
        for trigger in escalation_triggers
    ]
    escalation_issues.extend(all_critical_issues[:20])

    return await _create_review(
        session,
        paper_id=paper_id,
        family_id=paper.family_id,
        verdict="revision_needed",
        severity="critical",
        issues=escalation_issues,
        content=report_content,
        layer_summaries=layer_summaries,
        questions=questions_for_human,
        recommended_actions=recommended_actions,
        risk_assessment=risk_assessment,
    )


# ---------------------------------------------------------------------------
# Trigger identification
# ---------------------------------------------------------------------------


def _identify_triggers(
    by_stage: dict[str, Review], paper: Paper | None
) -> list[str]:
    """Identify all escalation triggers from review results."""
    triggers: list[str] = []

    l3 = by_stage.get("l3_method")
    l4 = by_stage.get("l4_adversarial")

    # Grade disagreement.
    if l3 and l4:
        l3_grade = VERDICT_GRADES.get(l3.verdict, 2)
        l4_grade = VERDICT_GRADES.get(l4.verdict, 2)
        if abs(l3_grade - l4_grade) > 1:
            triggers.append(
                f"L3/L4 disagree by >1 grade: "
                f"L3={l3.verdict}, L4={l4.verdict}"
            )

    # Unresolved critical issues.
    for stage, review in by_stage.items():
        if review.severity == "critical" and review.resolution_status == "open":
            triggers.append(
                f"Unresolved critical issue in {stage}"
            )

    # Legal/doctrinal uncertainty.
    for stage, review in by_stage.items():
        issues = _extract_issues(review)
        for issue in issues:
            msg = issue.get("message", "").lower()
            if any(kw in msg for kw in ["legal", "doctrinal", "jurisdiction"]):
                triggers.append(f"Legal/doctrinal uncertainty in {stage}")
                break

    # Benchmark-strong but misleading.
    if l3 and l4:
        if l3.verdict == "pass" and l4.verdict == "fail":
            triggers.append(
                "Benchmark-strong but adversarial-rejected: "
                "methodology passes but adversarial review kills it"
            )

    if not triggers:
        triggers.append("Escalation triggered by orchestrator override or manual request")

    return triggers


# ---------------------------------------------------------------------------
# Human question generation
# ---------------------------------------------------------------------------


def _generate_human_questions(
    by_stage: dict[str, Review],
    triggers: list[str],
    critical_issues: list[dict],
) -> list[str]:
    """Generate specific questions for the human reviewer."""
    questions: list[str] = []

    l3 = by_stage.get("l3_method")
    l4 = by_stage.get("l4_adversarial")

    # Question about disagreement.
    if l3 and l4 and l3.verdict != l4.verdict:
        questions.append(
            f"L3 method review says '{l3.verdict}' but L4 adversarial says "
            f"'{l4.verdict}'. Which assessment is more appropriate for this paper?"
        )

    # Questions about critical issues.
    for issue in critical_issues[:3]:
        check = issue.get("check", "unknown")
        msg = issue.get("message", "")
        questions.append(
            f"Critical issue [{check}]: {msg[:120]} -- Is this a genuine problem "
            f"or a false positive?"
        )

    # Standard questions.
    questions.append(
        "Does this paper meet the minimum quality bar for the target venue?"
    )
    questions.append(
        "Are there ethical or legal concerns that automated review cannot assess?"
    )

    # Legal/doctrinal questions.
    if any("legal" in t.lower() or "doctrinal" in t.lower() for t in triggers):
        questions.append(
            "Does the legal/doctrinal analysis correctly represent the current "
            "state of the law in the relevant jurisdiction?"
        )

    return questions


# ---------------------------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------------------------


def _generate_recommended_actions(
    by_stage: dict[str, Review],
    triggers: list[str],
    critical_issues: list[dict],
) -> list[str]:
    """Generate recommended actions for the escalation."""
    actions: list[str] = []

    l1 = by_stage.get("l1_structural")
    l2 = by_stage.get("l2_provenance")

    if l1 and l1.verdict == "fail":
        actions.append("BLOCK: Resolve structural integrity failures before proceeding.")

    if l2 and l2.verdict == "fail":
        actions.append("BLOCK: Fix provenance violations before any release decision.")

    if critical_issues:
        actions.append(
            f"REVIEW: {len(critical_issues)} critical issue(s) require human judgment."
        )

    if any("disagree" in t.lower() for t in triggers):
        actions.append(
            "ADJUDICATE: Resolve conflicting review verdicts before proceeding."
        )

    if any("legal" in t.lower() for t in triggers):
        actions.append("CONSULT: Obtain legal/domain expert opinion before release.")

    actions.append("DECIDE: Set release_status to 'candidate' or 'killed' after review.")

    return actions


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------


def _assess_risk(
    by_stage: dict[str, Review],
    critical_issues: list[dict],
    warnings: list[dict],
) -> dict:
    """Compute an overall risk assessment."""
    # Count severity indicators.
    fail_count = sum(1 for r in by_stage.values() if r.verdict == "fail")
    revision_count = sum(1 for r in by_stage.values() if r.verdict == "revision_needed")

    if fail_count >= 2:
        level = "high"
        confidence = "high"
        rationale = (
            f"{fail_count} layers returned 'fail'. "
            f"Paper likely has fundamental issues."
        )
    elif fail_count == 1 and len(critical_issues) >= 3:
        level = "high"
        confidence = "medium"
        rationale = (
            f"One layer failed with {len(critical_issues)} critical issues. "
            f"Substantial problems identified."
        )
    elif fail_count == 1:
        level = "medium"
        confidence = "medium"
        rationale = (
            "One layer failed. May be recoverable with revision."
        )
    elif revision_count >= 2:
        level = "medium"
        confidence = "medium"
        rationale = (
            f"{revision_count} layers request revision. "
            f"Paper needs work but is not fundamentally broken."
        )
    elif len(critical_issues) > 0:
        level = "low-medium"
        confidence = "low"
        rationale = (
            f"No outright failures but {len(critical_issues)} critical issues "
            f"and {len(warnings)} warnings remain."
        )
    else:
        level = "low"
        confidence = "high"
        rationale = "No critical issues. Escalation may be precautionary."

    return {
        "level": level,
        "confidence": confidence,
        "rationale": rationale,
        "fail_count": fail_count,
        "revision_count": revision_count,
        "critical_issues": len(critical_issues),
        "warnings": len(warnings),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_reviews(session: AsyncSession, paper_id: str) -> list[Review]:
    """Load all reviews for a paper, ordered by stage and creation time."""
    stmt = (
        select(Review)
        .where(Review.paper_id == paper_id)
        .order_by(Review.stage, Review.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper | None:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _extract_issues(review: Review) -> list[dict]:
    """Extract the issues list from a review's issues_json field."""
    if not review.issues_json:
        return []
    data = safe_json_loads(review.issues_json, [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("issues", [])
    return []


async def _create_review(
    session: AsyncSession,
    *,
    paper_id: str,
    family_id: str | None,
    verdict: str,
    severity: str,
    issues: list[dict],
    content: str,
    layer_summaries: list[dict] | None = None,
    questions: list[str] | None = None,
    recommended_actions: list[str] | None = None,
    risk_assessment: dict | None = None,
) -> Review:
    """Create and persist a Layer 5 Review record."""
    issues_payload: dict = {
        "issues": issues,
    }
    if layer_summaries is not None:
        issues_payload["layer_summaries"] = layer_summaries
    if questions is not None:
        issues_payload["questions_for_human"] = questions
    if recommended_actions is not None:
        issues_payload["recommended_actions"] = recommended_actions
    if risk_assessment is not None:
        issues_payload["risk_assessment"] = risk_assessment

    review = Review(
        paper_id=paper_id,
        stage="l5_human",
        model_used="system",
        verdict=verdict,
        content=content,
        severity=severity,
        resolution_status="escalated",
        family_id=family_id,
        review_rubric_version="escalation_v1",
        issues_json=json.dumps(issues_payload),
    )
    session.add(review)
    await session.flush()
    logger.info(
        "[%s] L5 human escalation: verdict=%s, triggers=%d",
        paper_id, verdict, len(issues),
    )
    return review
