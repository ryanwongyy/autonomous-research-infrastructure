"""Auto-classifies failures from review verdicts and issues."""

from __future__ import annotations

import logging
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failure_record import FailureRecord
from app.models.review import Review
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# Mapping from issue check names to failure types
ISSUE_TO_FAILURE_TYPE = {
    "source_drift": "source_drift",
    "stale_source": "source_drift",
    "hash_drift": "source_drift",
    "tier_violation": "data_error",
    "data_quality": "data_error",
    "missing_data": "data_error",
    "causal_language": "causal_overreach",
    "unsupported_causal": "causal_overreach",
    "over_generalization": "causal_overreach",
    "hallucination": "hallucination",
    "fabrication": "hallucination",
    "identification": "logic_error",
    "proof_error": "logic_error",
    "specification_error": "logic_error",
    "lock_violation": "design_violation",
    "lock_hash": "design_violation",
    "formatting": "formatting",
    "numbering": "formatting",
    "citation": "formatting",
}


def classify_failure(review: Review) -> FailureRecord | None:
    """Examine a review's verdict and issues to auto-classify failures.

    Returns a FailureRecord if a failure was detected, None otherwise.
    """
    if review.verdict == "pass":
        return None

    # Parse issues from JSON
    parsed = safe_json_loads(review.issues_json, [])
    issues = parsed.get("issues", []) if isinstance(parsed, dict) else parsed

    # Determine failure type from issues
    failure_type = "other"
    for issue in issues:
        check_name = issue.get("check", "")
        for keyword, ftype in ISSUE_TO_FAILURE_TYPE.items():
            if keyword in check_name.lower():
                failure_type = ftype
                break
        if failure_type != "other":
            break

    # Determine severity from review
    severity = review.severity if review.severity in ("low", "medium", "high", "critical") else "medium"

    return FailureRecord(
        paper_id=review.paper_id,
        family_id=review.family_id,
        failure_type=failure_type,
        severity=severity,
        detection_stage=review.stage,
        root_cause_category=failure_type,
    )


async def auto_record_failure(
    session: AsyncSession, review: Review
) -> FailureRecord | None:
    """Auto-classify and persist a failure from a review verdict."""
    record = classify_failure(review)
    if record:
        session.add(record)
        await session.flush()
        logger.info(
            "Auto-recorded failure: paper=%s, type=%s, stage=%s, severity=%s",
            record.paper_id, record.failure_type, record.detection_stage, record.severity,
        )
    return record


async def get_failure_distribution(
    session: AsyncSession, family_id: str | None = None
) -> dict:
    """Get failure counts by type, severity, and detection stage."""
    query = select(FailureRecord)
    if family_id:
        query = query.where(FailureRecord.family_id == family_id)

    result = await session.execute(query)
    records = result.scalars().all()

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_stage: dict[str, int] = {}

    for r in records:
        by_type[r.failure_type] = by_type.get(r.failure_type, 0) + 1
        by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        by_stage[r.detection_stage] = by_stage.get(r.detection_stage, 0) + 1

    return {
        "total": len(records),
        "by_type": by_type,
        "by_severity": by_severity,
        "by_stage": by_stage,
    }


async def get_failure_trends(
    session: AsyncSession, days: int = 90
) -> list[dict]:
    """Get failure counts grouped by date for recent period."""
    from datetime import datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await session.execute(
        select(FailureRecord).where(FailureRecord.created_at >= cutoff).order_by(FailureRecord.created_at)
    )
    records = result.scalars().all()

    # Group by date
    daily: dict[str, dict[str, int]] = {}
    for r in records:
        date_str = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
        if date_str not in daily:
            daily[date_str] = {"date": date_str, "total": 0}
        daily[date_str]["total"] += 1
        daily[date_str][r.failure_type] = daily[date_str].get(r.failure_type, 0) + 1

    return list(daily.values())
