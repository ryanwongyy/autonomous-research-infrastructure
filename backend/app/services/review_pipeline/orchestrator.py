"""5-Layer Review Orchestrator

Sequence:
1. L1 (Structural) -- must pass before proceeding
2. L2 (Provenance) -- must pass before proceeding
3. L3 (Method/Non-Claude) + L4 (Adversarial) -- run in parallel
4. L5 (Human Escalation) -- conditional, only if triggered

Decision rules:
- PASS: L1 pass, L2 pass, L3 not reject, L4 not reject, no escalation needed
- REVISION: L1/L2 fixable issues, or L3/L4 request revision
- REJECT: persistent replication failure, central unsupported claim,
          lockfile breach, benchmark failure after 2 loops
- ESCALATE: reviewer disagreement >1 grade, genuine legal uncertainty,
            benchmark-strong but misleading
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.review import Review
from app.utils import safe_json_loads

from app.services.review_pipeline.l1_structural import run_structural_review
from app.services.review_pipeline.l2_provenance import run_provenance_review
from app.services.review_pipeline.l3_method import run_method_review
from app.services.review_pipeline.l4_adversarial import run_adversarial_review
from app.services.review_pipeline.l5_human_escalation import (
    check_escalation_needed,
    generate_escalation_report,
)

logger = logging.getLogger(__name__)

# Maximum revision loops before hard reject.
MAX_REVISION_LOOPS = 2


async def run_review_pipeline(
    session: AsyncSession,
    paper_id: str,
) -> dict:
    """Run the full 5-layer review pipeline.

    Returns comprehensive review report with per-layer results and final decision.

    The report dict has the structure:
    {
        "paper_id": str,
        "decision": "pass" | "revision_needed" | "reject" | "escalate",
        "layers": {
            "l1_structural": {"verdict": str, "review_id": int, ...},
            "l2_provenance": {"verdict": str, "review_id": int, ...},
            "l3_method": {"verdict": str, "review_id": int, ...} | None,
            "l4_adversarial": {"verdict": str, "review_id": int, ...} | None,
            "l5_human": {"verdict": str, "review_id": int, ...} | None,
        },
        "summary": str,
        "escalated": bool,
        "started_at": str,
        "completed_at": str,
    }
    """
    started_at = datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "paper_id": paper_id,
        "decision": "pending",
        "layers": {},
        "summary": "",
        "escalated": False,
        "started_at": started_at.isoformat(),
        "completed_at": None,
    }

    # Verify paper exists.
    paper = await _load_paper(session, paper_id)
    if paper is None:
        report["decision"] = "reject"
        report["summary"] = f"Paper '{paper_id}' not found."
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    # Update paper status to 'reviewing'.
    await _set_paper_status(session, paper_id, status="reviewing", funnel_stage="reviewing")

    # ==================================================================
    # LAYER 1: Structural Integrity (must pass to proceed)
    # ==================================================================
    logger.info("[%s] Starting L1: Structural integrity check", paper_id)

    l1_review = await run_structural_review(session, paper_id)
    report["layers"]["l1_structural"] = _review_to_dict(l1_review)

    if l1_review.verdict == "fail":
        logger.warning("[%s] L1 FAILED -- pipeline halted", paper_id)
        report["decision"] = "reject"
        report["summary"] = (
            "Structural integrity check failed. "
            "Cannot proceed until structural issues are resolved. "
            f"Issues: {l1_review.content[:200]}"
        )
        await _set_paper_status(
            session, paper_id, status="reviewing", review_status="errors",
            funnel_stage="reviewing",
        )
        await session.commit()
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    if l1_review.verdict == "revision_needed":
        logger.info("[%s] L1 needs revision -- continuing with warnings", paper_id)

    # ==================================================================
    # LAYER 2: Provenance Verification (must pass to proceed)
    # ==================================================================
    logger.info("[%s] Starting L2: Provenance verification", paper_id)

    l2_review = await run_provenance_review(session, paper_id)
    report["layers"]["l2_provenance"] = _review_to_dict(l2_review)

    if l2_review.verdict == "fail":
        logger.warning("[%s] L2 FAILED -- pipeline halted", paper_id)
        report["decision"] = "reject"
        report["summary"] = (
            "Provenance verification failed. "
            "Claims cannot be verified against sources. "
            f"Issues: {l2_review.content[:200]}"
        )
        await _set_paper_status(
            session, paper_id, status="reviewing", review_status="errors",
            funnel_stage="reviewing",
        )
        await session.commit()
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    if l2_review.verdict == "revision_needed":
        logger.info("[%s] L2 needs revision -- continuing with warnings", paper_id)

    # ==================================================================
    # LAYERS 3 & 4: Method Review + Adversarial Review (parallel)
    # ==================================================================
    logger.info("[%s] Starting L3+L4: Method and Adversarial reviews (parallel)", paper_id)

    l3_result, l4_result = await asyncio.gather(
        _safe_run(run_method_review, session, paper_id, "l3_method"),
        _safe_run(run_adversarial_review, session, paper_id, "l4_adversarial"),
    )

    l3_review, l3_error = l3_result
    l4_review, l4_error = l4_result

    if l3_review:
        report["layers"]["l3_method"] = _review_to_dict(l3_review)
    else:
        report["layers"]["l3_method"] = {"verdict": "error", "error": str(l3_error)}
        logger.error("[%s] L3 method review failed: %s", paper_id, l3_error)

    if l4_review:
        report["layers"]["l4_adversarial"] = _review_to_dict(l4_review)
    else:
        report["layers"]["l4_adversarial"] = {"verdict": "error", "error": str(l4_error)}
        logger.error("[%s] L4 adversarial review failed: %s", paper_id, l4_error)

    # ==================================================================
    # DECISION LOGIC (pre-escalation)
    # ==================================================================
    l3_verdict = l3_review.verdict if l3_review else "fail"
    l4_verdict = l4_review.verdict if l4_review else "fail"

    # Immediate reject conditions.
    if l3_verdict == "fail" and l4_verdict == "fail":
        logger.warning("[%s] Both L3 and L4 reject -- paper rejected", paper_id)
        report["decision"] = "reject"
        report["summary"] = (
            "Both method review and adversarial review rejected this paper."
        )
        await _set_paper_status(
            session, paper_id, status="reviewing", review_status="errors",
            funnel_stage="reviewing",
        )
        await session.commit()
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    # ==================================================================
    # LAYER 5: Human Escalation (conditional)
    # ==================================================================
    logger.info("[%s] Checking escalation conditions", paper_id)

    needs_escalation = await check_escalation_needed(session, paper_id)

    if needs_escalation:
        logger.info("[%s] Escalation triggered -- generating report", paper_id)
        l5_review = await generate_escalation_report(session, paper_id)
        report["layers"]["l5_human"] = _review_to_dict(l5_review)
        report["escalated"] = True
        report["decision"] = "escalate"
        report["summary"] = (
            "Paper escalated to human review. "
            "Automated reviewers disagreed or flagged uncertainty. "
            "See L5 report for details."
        )
        await session.commit()
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    # ==================================================================
    # FINAL DECISION (no escalation needed)
    # ==================================================================
    decision = _compute_final_decision(
        l1_verdict=l1_review.verdict,
        l2_verdict=l2_review.verdict,
        l3_verdict=l3_verdict,
        l4_verdict=l4_verdict,
    )

    report["decision"] = decision
    report["summary"] = _build_final_summary(
        decision=decision,
        l1_verdict=l1_review.verdict,
        l2_verdict=l2_review.verdict,
        l3_verdict=l3_verdict,
        l4_verdict=l4_verdict,
    )

    # Update paper status based on decision.
    if decision == "pass":
        await _set_paper_status(
            session, paper_id,
            status="candidate",
            review_status="peer_reviewed",
            funnel_stage="candidate",
            release_status="candidate",
        )
    elif decision == "revision_needed":
        await _set_paper_status(
            session, paper_id,
            status="revision",
            review_status="issues",
            funnel_stage="revision",
        )
    elif decision == "reject":
        await _set_paper_status(
            session, paper_id,
            status="reviewing",
            review_status="errors",
            funnel_stage="reviewing",
        )

    await session.commit()

    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info(
        "[%s] Review pipeline completed: decision=%s", paper_id, decision
    )
    return report


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


def _compute_final_decision(
    *,
    l1_verdict: str,
    l2_verdict: str,
    l3_verdict: str,
    l4_verdict: str,
) -> str:
    """Compute the final pipeline decision from layer verdicts.

    Decision rules:
    - PASS: all layers pass (L1/L2 pass, L3/L4 not fail)
    - REVISION: any layer requests revision but none fail (except L1/L2
      revision_needed is tolerated alongside L3/L4 pass)
    - REJECT: any critical layer fails outright
    """
    # Any hard fail in L3 or L4 means reject.
    if l3_verdict == "fail" or l4_verdict == "fail":
        return "reject"

    # If L1 or L2 had revision_needed, and L3/L4 also need revision,
    # the paper needs revision.
    verdicts = [l1_verdict, l2_verdict, l3_verdict, l4_verdict]
    if any(v == "revision_needed" for v in verdicts):
        return "revision_needed"

    # All pass.
    return "pass"


def _build_final_summary(
    *,
    decision: str,
    l1_verdict: str,
    l2_verdict: str,
    l3_verdict: str,
    l4_verdict: str,
) -> str:
    """Build a human-readable summary of the pipeline result."""
    parts = [
        f"Pipeline decision: {decision.upper()}",
        f"  L1 Structural: {l1_verdict}",
        f"  L2 Provenance: {l2_verdict}",
        f"  L3 Method: {l3_verdict}",
        f"  L4 Adversarial: {l4_verdict}",
    ]

    if decision == "pass":
        parts.append("Paper passed all automated review layers.")
    elif decision == "revision_needed":
        revision_layers = []
        for name, v in [
            ("L1", l1_verdict), ("L2", l2_verdict),
            ("L3", l3_verdict), ("L4", l4_verdict),
        ]:
            if v == "revision_needed":
                revision_layers.append(name)
        parts.append(f"Revision needed in: {', '.join(revision_layers)}")
    elif decision == "reject":
        parts.append("Paper rejected by automated review.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _safe_run(
    func,
    session: AsyncSession,
    paper_id: str,
    layer_name: str,
) -> tuple[Review | None, Exception | None]:
    """Run a review function, catching exceptions so gather continues."""
    try:
        review = await func(session, paper_id)
        return review, None
    except Exception as exc:
        logger.error("[%s] %s failed with exception: %s", paper_id, layer_name, exc)
        return None, exc


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper | None:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _set_paper_status(
    session: AsyncSession,
    paper_id: str,
    *,
    status: str | None = None,
    review_status: str | None = None,
    funnel_stage: str | None = None,
    release_status: str | None = None,
) -> None:
    """Update paper status fields."""
    values: dict[str, Any] = {}
    if status is not None:
        values["status"] = status
    if review_status is not None:
        values["review_status"] = review_status
    if funnel_stage is not None:
        values["funnel_stage"] = funnel_stage
    if release_status is not None:
        values["release_status"] = release_status

    if values:
        await session.execute(
            update(Paper).where(Paper.id == paper_id).values(**values)
        )


def _review_to_dict(review: Review) -> dict:
    """Convert a Review object to a summary dict for the pipeline report."""
    issues_count = 0
    data = safe_json_loads(review.issues_json, [])
    if isinstance(data, list):
        issues_count = len(data)
    elif isinstance(data, dict):
        issues_count = len(data.get("issues", []))

    return {
        "review_id": review.id,
        "verdict": review.verdict,
        "severity": review.severity,
        "model_used": review.model_used,
        "issues_count": issues_count,
        "resolution_status": review.resolution_status,
        "content_preview": review.content[:300] if review.content else "",
    }
