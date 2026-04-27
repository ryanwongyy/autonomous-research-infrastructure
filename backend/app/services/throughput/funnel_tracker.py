"""Tracks papers through the production funnel.
Provides conversion rates, bottleneck detection, and projection."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper

logger = logging.getLogger(__name__)

FUNNEL_STAGES_ORDERED = [
    "idea",
    "screened",
    "locked",
    "ingesting",
    "analyzing",
    "drafting",
    "reviewing",
    "revision",
    "benchmark",
    "candidate",
    "submitted",
    "public",
]

TERMINAL_STAGES = ["public", "killed"]

# Annual throughput targets (domain defaults)
ANNUAL_TARGETS = {
    "ideas": 5000,
    "screened": 2500,
    "locked": 300,
    "submission_ready": 28,
    "flagship": 3,
    "elite_field": 6,
}


async def get_funnel_snapshot(
    session: AsyncSession,
    family_id: str | None = None,
) -> dict:
    """Get current funnel snapshot -- count of papers at each stage.
    Returns {
        "stages": {stage: count},
        "killed": count,
        "total_active": count,
        "total_completed": count,
    }
    """
    query = select(Paper.funnel_stage, func.count()).group_by(Paper.funnel_stage)
    if family_id:
        query = query.where(Paper.family_id == family_id)

    result = await session.execute(query)
    raw_counts = {row[0]: row[1] for row in result.all()}

    stages = {}
    for stage in FUNNEL_STAGES_ORDERED:
        stages[stage] = raw_counts.get(stage, 0)

    killed = raw_counts.get("killed", 0)
    total_completed = stages.get("public", 0)
    total_active = sum(stages.values()) - total_completed

    return {
        "family_id": family_id,
        "stages": stages,
        "killed": killed,
        "total_active": total_active,
        "total_completed": total_completed,
    }


async def get_conversion_rates(
    session: AsyncSession,
    family_id: str | None = None,
    days: int = 365,
) -> dict:
    """Compute stage-to-stage conversion rates.

    For each adjacent pair of funnel stages, the conversion rate is the number
    of papers that have reached stage N+1 (or beyond) divided by the number
    that have reached stage N (or beyond).

    Returns {
        "conversions": [
            {"from": "idea", "to": "screened", "rate": 0.10, "count": 500, "converted": 50}
        ],
        "overall_rate": 0.0056,  # idea -> public
        "period_days": 365
    }
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)

    query = select(Paper.funnel_stage, func.count()).group_by(Paper.funnel_stage)
    if family_id:
        query = query.where(Paper.family_id == family_id)
    query = query.where(Paper.created_at >= cutoff)

    result = await session.execute(query)
    stage_counts = {row[0]: row[1] for row in result.all()}

    # Build cumulative counts: papers at stage N or beyond
    cumulative = {}
    running_total = 0
    for stage in reversed(FUNNEL_STAGES_ORDERED):
        running_total += stage_counts.get(stage, 0)
        cumulative[stage] = running_total

    # Also count killed papers toward their last active stage
    # (they entered the funnel but didn't convert further)
    killed_count = stage_counts.get("killed", 0)
    # killed papers were at least at 'idea' stage
    if killed_count > 0:
        cumulative["idea"] = cumulative.get("idea", 0) + killed_count

    conversions = []
    for i in range(len(FUNNEL_STAGES_ORDERED) - 1):
        from_stage = FUNNEL_STAGES_ORDERED[i]
        to_stage = FUNNEL_STAGES_ORDERED[i + 1]
        count_at_from = cumulative.get(from_stage, 0)
        count_at_to = cumulative.get(to_stage, 0)

        rate = count_at_to / count_at_from if count_at_from > 0 else 0.0

        conversions.append(
            {
                "from": from_stage,
                "to": to_stage,
                "rate": round(rate, 4),
                "count": count_at_from,
                "converted": count_at_to,
            }
        )

    # Overall: idea -> public
    total_ideas = cumulative.get("idea", 0)
    total_public = cumulative.get("public", 0)
    overall_rate = total_public / total_ideas if total_ideas > 0 else 0.0

    return {
        "conversions": conversions,
        "overall_rate": round(overall_rate, 6),
        "period_days": days,
        "family_id": family_id,
    }


async def detect_bottlenecks(
    session: AsyncSession,
    family_id: str | None = None,
) -> list[dict]:
    """Find stages where papers are stuck.
    A bottleneck = stage with many papers and low conversion rate.

    We estimate "stuck" papers as those at a given stage whose updated_at
    is older than a threshold. Severity is based on the count and age.

    Returns [{"stage": str, "stuck_count": int, "avg_days_in_stage": float, "severity": str}]
    """
    now = datetime.now(UTC)
    bottlenecks = []

    # Thresholds for how long a paper can sit in a stage before it's considered stuck
    stage_thresholds_days = {
        "idea": 14,
        "screened": 7,
        "locked": 5,
        "ingesting": 3,
        "analyzing": 5,
        "drafting": 7,
        "reviewing": 10,
        "revision": 14,
        "benchmark": 5,
        "candidate": 14,
        "submitted": 30,
    }

    for stage in FUNNEL_STAGES_ORDERED:
        if stage == "public":
            continue  # public is terminal, not a bottleneck

        threshold_days = stage_thresholds_days.get(stage, 14)
        cutoff = now - timedelta(days=threshold_days)

        query = select(Paper).where(
            Paper.funnel_stage == stage,
            Paper.updated_at < cutoff,
        )
        if family_id:
            query = query.where(Paper.family_id == family_id)

        result = await session.execute(query)
        stuck_papers = result.scalars().all()

        if not stuck_papers:
            continue

        stuck_count = len(stuck_papers)
        total_days = sum(
            (
                now
                - (
                    p.updated_at.replace(tzinfo=UTC)
                    if p.updated_at.tzinfo is None
                    else p.updated_at
                )
            ).days
            for p in stuck_papers
        )
        avg_days = total_days / stuck_count if stuck_count > 0 else 0.0

        # Severity based on count and age
        if stuck_count >= 20 or avg_days >= threshold_days * 3:
            severity = "critical"
        elif stuck_count >= 10 or avg_days >= threshold_days * 2:
            severity = "high"
        elif stuck_count >= 5 or avg_days >= threshold_days * 1.5:
            severity = "medium"
        else:
            severity = "low"

        bottlenecks.append(
            {
                "stage": stage,
                "stuck_count": stuck_count,
                "avg_days_in_stage": round(avg_days, 1),
                "threshold_days": threshold_days,
                "severity": severity,
            }
        )

    # Sort by severity then count
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    bottlenecks.sort(key=lambda b: (severity_order.get(b["severity"], 4), -b["stuck_count"]))

    return bottlenecks


async def project_annual_output(
    session: AsyncSession,
    days_of_data: int = 90,
) -> dict:
    """Project annual output based on recent throughput.

    Looks at papers that reached each key milestone in the recent window,
    then extrapolates to 365 days.

    Returns {
        "projected_annual": {
            "ideas": int,
            "submission_ready": int,
            "flagship": int,
            "elite_field": int
        },
        "targets": {... from domain config ...},
        "on_track": bool,
        "gap_analysis": str
    }
    """
    cutoff = datetime.now(UTC) - timedelta(days=days_of_data)
    scale_factor = 365 / days_of_data

    # Count papers created (ideas generated) in the window
    ideas_result = await session.execute(
        select(func.count()).select_from(Paper).where(Paper.created_at >= cutoff)
    )
    recent_ideas = ideas_result.scalar() or 0

    # Count papers that reached 'candidate' or beyond in the window
    # (submission-ready)
    submission_stages = ["candidate", "submitted", "public"]
    submission_result = await session.execute(
        select(func.count())
        .select_from(Paper)
        .where(Paper.funnel_stage.in_(submission_stages))
        .where(Paper.updated_at >= cutoff)
    )
    recent_submission_ready = submission_result.scalar() or 0

    # Count papers that reached 'submitted' or 'public' in the window
    submitted_result = await session.execute(
        select(func.count())
        .select_from(Paper)
        .where(Paper.funnel_stage.in_(["submitted", "public"]))
        .where(Paper.updated_at >= cutoff)
    )
    recent_submitted = submitted_result.scalar() or 0

    # Count papers that reached 'public' in the window
    public_result = await session.execute(
        select(func.count())
        .select_from(Paper)
        .where(Paper.funnel_stage == "public")
        .where(Paper.updated_at >= cutoff)
    )
    recent_public = public_result.scalar() or 0

    projected = {
        "ideas": round(recent_ideas * scale_factor),
        "submission_ready": round(recent_submission_ready * scale_factor),
        "flagship": round(recent_submitted * scale_factor),
        "elite_field": round(recent_public * scale_factor),
    }

    targets = ANNUAL_TARGETS

    # Determine if on track -- at minimum must meet submission_ready target
    on_track = (
        projected["ideas"] >= targets["ideas"] * 0.8
        and projected["submission_ready"] >= targets["submission_ready"] * 0.8
    )

    # Gap analysis
    gaps = []
    for key in ["ideas", "submission_ready", "flagship", "elite_field"]:
        target = targets.get(key, 0)
        actual = projected.get(key, 0)
        if target > 0 and actual < target:
            deficit = target - actual
            pct = round((actual / target) * 100, 1) if target > 0 else 0
            gaps.append(
                f"{key}: projected {actual} vs target {target} ({pct}% of target, deficit {deficit})"
            )

    if gaps:
        gap_analysis = "Behind target on: " + "; ".join(gaps)
    else:
        gap_analysis = "All projections meet or exceed annual targets."

    return {
        "projected_annual": projected,
        "targets": targets,
        "on_track": on_track,
        "gap_analysis": gap_analysis,
        "data_window_days": days_of_data,
    }
