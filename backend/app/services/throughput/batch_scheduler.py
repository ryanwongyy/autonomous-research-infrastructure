"""Manages daily batch sizes to hit annual throughput targets."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.services.throughput.funnel_tracker import ANNUAL_TARGETS, FUNNEL_STAGES_ORDERED

logger = logging.getLogger(__name__)

# Map annual targets to their corresponding funnel stages
_STAGE_TO_TARGET_KEY = {
    "idea": "ideas",
    "screened": "screened",
    "locked": "locked",
    "candidate": "submission_ready",
}


async def compute_daily_targets(
    session: AsyncSession,
) -> dict:
    """Based on annual targets and current pipeline state, compute daily work targets.

    Annual targets (from domain config):
    - 5000 ideas -> ~14/day
    - 2500 screened -> ~7/day
    - 300 locked plans -> ~1/day (approx 0.82/day)
    - 28 submission-ready -> ~0.54/week (approx 0.08/day)

    Adjusts targets based on year-to-date progress: if behind, ramp up;
    if ahead, maintain steady pace.

    Returns daily target counts per pipeline stage.
    """
    now = datetime.now(UTC)
    year_start = datetime(now.year, 1, 1, tzinfo=UTC)
    days_elapsed = max((now - year_start).days, 1)
    days_remaining = max(365 - days_elapsed, 1)

    targets = ANNUAL_TARGETS

    # Count year-to-date completions for each target stage
    ytd_counts = {}
    for stage, target_key in _STAGE_TO_TARGET_KEY.items():
        # Count papers currently at this stage or beyond
        stage_idx = FUNNEL_STAGES_ORDERED.index(stage) if stage in FUNNEL_STAGES_ORDERED else 0
        at_or_beyond_stages = FUNNEL_STAGES_ORDERED[stage_idx:]

        result = await session.execute(
            select(func.count())
            .select_from(Paper)
            .where(Paper.funnel_stage.in_(at_or_beyond_stages))
            .where(Paper.created_at >= year_start)
        )
        ytd_counts[target_key] = result.scalar() or 0

    daily_targets = {}
    for target_key, annual_target in targets.items():
        ytd = ytd_counts.get(target_key, 0)
        remaining_needed = max(annual_target - ytd, 0)

        # Daily rate needed for the rest of the year
        daily_rate = remaining_needed / days_remaining

        # Straight annual daily rate (for reference)
        baseline_daily = annual_target / 365

        daily_targets[target_key] = {
            "annual_target": annual_target,
            "ytd_completed": ytd,
            "remaining": remaining_needed,
            "daily_rate_needed": round(daily_rate, 2),
            "baseline_daily_rate": round(baseline_daily, 2),
            "on_pace": ytd >= (annual_target * days_elapsed / 365),
        }

    return {
        "date": now.date().isoformat(),
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "daily_targets": daily_targets,
    }


async def get_work_queue(
    session: AsyncSession,
    family_id: str | None = None,
) -> dict:
    """Get the work queue -- papers ready for the next pipeline stage.

    Prioritized by:
    1. Family balance (underserved families first)
    2. Age (oldest first)
    3. Screening score (highest first)

    Groups papers by their current stage and what work they need next.
    """
    # Get all active families and their current paper counts
    families_result = await session.execute(
        select(PaperFamily).where(PaperFamily.active.is_(True))
    )
    families = families_result.scalars().all()

    family_paper_counts = {}
    for fam in families:
        count_result = await session.execute(
            select(func.count())
            .select_from(Paper)
            .where(Paper.family_id == fam.id)
            .where(Paper.funnel_stage != "killed")
        )
        family_paper_counts[fam.id] = {
            "count": count_result.scalar() or 0,
            "name": fam.short_name,
            "max_share": fam.max_portfolio_share,
        }

    total_papers = sum(f["count"] for f in family_paper_counts.values())

    # Compute family balance scores: lower share = higher priority
    family_priority = {}
    for fam_id, info in family_paper_counts.items():
        current_share = info["count"] / total_papers if total_papers > 0 else 0.0
        # Priority score: how far below max_share. Higher = more underserved.
        family_priority[fam_id] = info["max_share"] - current_share

    # Define what "ready for next stage" means
    stage_transitions = {
        "idea": "Ready for screening",
        "screened": "Ready for design lock",
        "locked": "Ready for data ingestion",
        "ingesting": "Ready for analysis",
        "analyzing": "Ready for drafting",
        "drafting": "Ready for review",
        "reviewing": "Awaiting review completion",
        "revision": "Ready for re-review",
        "benchmark": "Ready for candidate release",
        "candidate": "Ready for submission",
        "submitted": "Awaiting publication confirmation",
    }

    work_queue = {}

    for stage, description in stage_transitions.items():
        query = select(Paper).where(Paper.funnel_stage == stage)
        if family_id:
            query = query.where(Paper.family_id == family_id)

        result = await session.execute(query)
        papers = result.scalars().all()

        if not papers:
            continue

        # Sort papers by priority
        def sort_key(paper):
            # Family balance priority (higher = process first)
            fam_score = family_priority.get(paper.family_id, 0.0) if paper.family_id else 0.0
            # Age priority (older papers first, so negate updated_at)
            age_score = -(paper.updated_at or paper.created_at).timestamp()
            # Screening score (higher is better)
            screen_score = paper.overall_screening_score or 0.0
            return (-fam_score, age_score, -screen_score)

        papers.sort(key=sort_key)

        items = []
        for p in papers:
            age_days = 0
            ref_time = p.updated_at or p.created_at
            if ref_time:
                ref_aware = ref_time.replace(tzinfo=UTC) if ref_time.tzinfo is None else ref_time
                age_days = (datetime.now(UTC) - ref_aware).days

            items.append({
                "paper_id": p.id,
                "title": p.title,
                "family_id": p.family_id,
                "days_in_stage": age_days,
                "screening_score": p.overall_screening_score,
                "family_priority": round(family_priority.get(p.family_id, 0.0), 3) if p.family_id else None,
            })

        work_queue[stage] = {
            "description": description,
            "count": len(items),
            "papers": items,
        }

    total_queued = sum(q["count"] for q in work_queue.values())

    return {
        "family_id": family_id,
        "total_queued": total_queued,
        "stages": work_queue,
        "family_balance": {
            fam_id: {
                "name": info["name"],
                "paper_count": info["count"],
                "current_share": round(info["count"] / total_papers, 3) if total_papers > 0 else 0.0,
                "max_share": info["max_share"],
                "priority_score": round(family_priority.get(fam_id, 0.0), 3),
            }
            for fam_id, info in family_paper_counts.items()
        },
    }
