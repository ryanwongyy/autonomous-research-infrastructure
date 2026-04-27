"""Service for tracking submission outcomes and computing acceptance rates."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.submission_outcome import SubmissionOutcome

logger = logging.getLogger(__name__)


async def record_outcome(
    session: AsyncSession,
    paper_id: str,
    venue_name: str,
    submitted_date: str,
    decision: str | None = None,
    decision_date: str | None = None,
    revision_rounds: int = 0,
    reviewer_feedback_summary: str | None = None,
) -> SubmissionOutcome:
    """Record a submission outcome for a paper."""
    from datetime import datetime

    outcome = SubmissionOutcome(
        paper_id=paper_id,
        venue_name=venue_name,
        submitted_date=datetime.fromisoformat(submitted_date),
        decision=decision,
        decision_date=datetime.fromisoformat(decision_date) if decision_date else None,
        revision_rounds=revision_rounds,
        reviewer_feedback_summary=reviewer_feedback_summary,
    )
    session.add(outcome)
    await session.flush()
    logger.info("Recorded outcome for paper %s at %s: %s", paper_id, venue_name, decision)
    return outcome


async def get_acceptance_rates(
    session: AsyncSession,
    family_id: str | None = None,
) -> dict:
    """Compute acceptance rates, optionally filtered by family."""
    query = select(SubmissionOutcome)
    if family_id:
        query = query.join(Paper, SubmissionOutcome.paper_id == Paper.id).where(
            Paper.family_id == family_id
        )

    result = await session.execute(query)
    outcomes = result.scalars().all()

    total = len(outcomes)
    if total == 0:
        return {
            "total": 0,
            "accepted": 0,
            "rejected": 0,
            "desk_reject": 0,
            "r_and_r": 0,
            "pending": 0,
            "acceptance_rate": 0.0,
        }

    accepted = sum(1 for o in outcomes if o.decision == "accepted")
    rejected = sum(1 for o in outcomes if o.decision == "rejected")
    desk_reject = sum(1 for o in outcomes if o.decision == "desk_reject")
    r_and_r = sum(1 for o in outcomes if o.decision == "r_and_r")
    pending = sum(1 for o in outcomes if o.decision is None)

    decided = accepted + rejected + desk_reject
    acceptance_rate = accepted / decided if decided > 0 else 0.0

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "desk_reject": desk_reject,
        "r_and_r": r_and_r,
        "pending": pending,
        "acceptance_rate": round(acceptance_rate, 4),
    }


async def get_outcomes_dashboard(session: AsyncSession) -> dict:
    """Aggregated outcomes dashboard data."""
    overall = await get_acceptance_rates(session)

    families_result = await session.execute(select(PaperFamily).where(PaperFamily.active.is_(True)))
    families = families_result.scalars().all()

    per_family = []
    for f in families:
        rates = await get_acceptance_rates(session, family_id=f.id)
        if rates["total"] > 0:
            per_family.append(
                {
                    "family_id": f.id,
                    "short_name": f.short_name,
                    **rates,
                }
            )

    return {"overall": overall, "per_family": per_family}
