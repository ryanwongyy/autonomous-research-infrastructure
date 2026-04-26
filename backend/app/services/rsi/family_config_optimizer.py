"""Tier 2a: Quarterly family health assessment and config optimization."""

from __future__ import annotations

import logging

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failure_record import FailureRecord
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating
from app.models.reliability_metric import ReliabilityMetric
from app.models.submission_outcome import SubmissionOutcome
from app.services.rsi.experiment_manager import create_experiment
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# Weights for composite health score
_W_ACCEPTANCE = 0.35
_W_RATING = 0.30
_W_RELIABILITY = 0.35


async def compute_family_health(session: AsyncSession, family_id: str) -> dict:
    """Compute comprehensive health report for a paper family.

    Returns a dict with paper counts, acceptance rates, tournament stats,
    failure rates, reliability scores, venue/method breakdowns, and a
    composite 0-1 health score.
    """
    # -- paper count ----------------------------------------------------------
    paper_count_result = await session.execute(
        select(func.count()).select_from(Paper).where(Paper.family_id == family_id)
    )
    paper_count: int = paper_count_result.scalar() or 0

    if paper_count == 0:
        return {
            "family_id": family_id,
            "paper_count": 0,
            "acceptance_rate": 0.0,
            "avg_tournament_rank": 0.0,
            "avg_conservative_rating": 0.0,
            "failure_rate": 0.0,
            "top_failure_types": [],
            "reliability_scores": {},
            "venue_performance": [],
            "method_performance": [],
            "health_score": 0.0,
        }

    # -- acceptance rate & venue performance ----------------------------------
    venue_stats_result = await session.execute(
        select(
            SubmissionOutcome.venue_name,
            func.count().label("submitted"),
            func.sum(
                case((SubmissionOutcome.decision == "accepted", 1), else_=0)
            ).label("accepted"),
        )
        .join(Paper, Paper.id == SubmissionOutcome.paper_id)
        .where(Paper.family_id == family_id)
        .group_by(SubmissionOutcome.venue_name)
    )
    venue_rows = venue_stats_result.all()

    venue_performance: list[dict] = []
    total_submitted = 0
    total_accepted = 0
    for venue_name, submitted, accepted in venue_rows:
        submitted = submitted or 0
        accepted = accepted or 0
        total_submitted += submitted
        total_accepted += accepted
        rate = accepted / submitted if submitted > 0 else 0.0
        venue_performance.append({
            "venue": venue_name,
            "submitted": submitted,
            "accepted": accepted,
            "rate": round(rate, 4),
        })

    acceptance_rate = total_accepted / total_submitted if total_submitted > 0 else 0.0

    # -- tournament stats (Rating) -------------------------------------------
    rating_stats_result = await session.execute(
        select(
            func.avg(Rating.rank).label("avg_rank"),
            func.avg(Rating.conservative_rating).label("avg_conservative"),
        ).where(Rating.family_id == family_id)
    )
    rating_row = rating_stats_result.one_or_none()
    avg_rank = float(rating_row.avg_rank) if rating_row and rating_row.avg_rank is not None else 0.0
    avg_conservative = float(rating_row.avg_conservative) if rating_row and rating_row.avg_conservative is not None else 0.0

    # -- failure stats --------------------------------------------------------
    failure_count_result = await session.execute(
        select(func.count()).select_from(FailureRecord).where(
            FailureRecord.family_id == family_id
        )
    )
    failure_count: int = failure_count_result.scalar() or 0
    failure_rate = failure_count / paper_count if paper_count > 0 else 0.0

    top_failures_result = await session.execute(
        select(
            FailureRecord.failure_type,
            func.count().label("cnt"),
        )
        .where(FailureRecord.family_id == family_id)
        .group_by(FailureRecord.failure_type)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_failure_types = [
        {"type": row.failure_type, "count": row.cnt}
        for row in top_failures_result.all()
    ]

    # -- reliability scores ---------------------------------------------------
    reliability_result = await session.execute(
        select(
            ReliabilityMetric.metric_type,
            func.avg(ReliabilityMetric.value).label("avg_val"),
        )
        .where(ReliabilityMetric.family_id == family_id)
        .group_by(ReliabilityMetric.metric_type)
    )
    reliability_scores: dict[str, float] = {
        row.metric_type: round(float(row.avg_val), 4)
        for row in reliability_result.all()
    }

    # -- method performance ---------------------------------------------------
    method_result = await session.execute(
        select(
            Paper.method,
            func.count().label("cnt"),
            func.avg(Rating.conservative_rating).label("avg_rating"),
        )
        .outerjoin(Rating, Rating.paper_id == Paper.id)
        .where(Paper.family_id == family_id, Paper.method.isnot(None))
        .group_by(Paper.method)
        .order_by(func.avg(Rating.conservative_rating).desc())
    )
    method_performance = [
        {
            "method": row.method,
            "count": row.cnt,
            "avg_rating": round(float(row.avg_rating), 4) if row.avg_rating is not None else 0.0,
        }
        for row in method_result.all()
    ]

    # -- composite health score -----------------------------------------------
    # Normalize acceptance_rate (already 0-1)
    # Normalize avg_conservative: use sigmoid-like clamp into 0-1
    #   conservative_rating typically ranges -25..+25; map via (x + 25) / 50
    norm_rating = max(0.0, min(1.0, (avg_conservative + 25.0) / 50.0))
    # Reliability component: average of all reliability metric values (assumed 0-1 range)
    if reliability_scores:
        avg_reliability = sum(reliability_scores.values()) / len(reliability_scores)
    else:
        avg_reliability = 0.0
    # Penalize by failure rate (1 - failure_rate clamped to [0,1])
    failure_penalty = max(0.0, 1.0 - failure_rate)

    health_score = (
        _W_ACCEPTANCE * acceptance_rate
        + _W_RATING * norm_rating
        + _W_RELIABILITY * avg_reliability
    ) * failure_penalty

    health_score = round(max(0.0, min(1.0, health_score)), 4)

    return {
        "family_id": family_id,
        "paper_count": paper_count,
        "acceptance_rate": round(acceptance_rate, 4),
        "avg_tournament_rank": round(avg_rank, 2),
        "avg_conservative_rating": round(avg_conservative, 4),
        "failure_rate": round(failure_rate, 4),
        "top_failure_types": top_failure_types,
        "reliability_scores": reliability_scores,
        "venue_performance": venue_performance,
        "method_performance": method_performance,
        "health_score": health_score,
    }


async def propose_config_changes(
    session: AsyncSession,
    family_id: str,
    health_report: dict,
) -> dict:
    """Propose configuration changes based on a family health report.

    Analyses venue performance, method performance, and failure patterns to
    generate concrete suggestions.  Creates an RSI experiment to track them.
    """
    changes: list[dict] = []
    rationale_parts: list[str] = []

    # -- Load current family config -------------------------------------------
    fam_result = await session.execute(
        select(PaperFamily).where(PaperFamily.id == family_id)
    )
    family = fam_result.scalar_one_or_none()
    if family is None:
        raise ValueError(f"PaperFamily '{family_id}' not found")

    venue_ladder: dict = safe_json_loads(family.venue_ladder, {})
    accepted_methods: list = safe_json_loads(family.accepted_methods, [])
    mandatory_checks: list = safe_json_loads(family.mandatory_checks, [])

    # -- Venue ladder analysis ------------------------------------------------
    venue_perf = {v["venue"]: v for v in health_report.get("venue_performance", [])}

    # Check if flagship venues have 0% but elite_field venues have > 0%
    flagship_venues = venue_ladder.get("flagship", [])
    elite_venues = venue_ladder.get("elite_field", [])

    flagship_accepted = sum(
        venue_perf.get(v, {}).get("accepted", 0) for v in flagship_venues
    )
    flagship_submitted = sum(
        venue_perf.get(v, {}).get("submitted", 0) for v in flagship_venues
    )
    elite_accepted = sum(
        venue_perf.get(v, {}).get("accepted", 0) for v in elite_venues
    )
    elite_submitted = sum(
        venue_perf.get(v, {}).get("submitted", 0) for v in elite_venues
    )

    flagship_rate = flagship_accepted / flagship_submitted if flagship_submitted > 0 else 0.0
    elite_rate = elite_accepted / elite_submitted if elite_submitted > 0 else 0.0

    if flagship_submitted > 0 and flagship_rate == 0.0 and elite_rate > 0.0:
        changes.append({
            "field": "venue_ladder",
            "action": "reorder",
            "detail": (
                f"Flagship venues ({', '.join(flagship_venues)}) have 0% acceptance "
                f"while elite_field venues have {elite_rate:.0%}. "
                "Consider promoting elite_field venues to primary targets."
            ),
        })
        rationale_parts.append("venue ladder misaligned with acceptance outcomes")

    # -- Method performance analysis ------------------------------------------
    method_perf = health_report.get("method_performance", [])
    if len(method_perf) >= 2:
        top_method = method_perf[0]
        # Check if the top-performing method is not already first in accepted_methods
        if accepted_methods and top_method["method"] not in accepted_methods[:1]:
            changes.append({
                "field": "accepted_methods",
                "action": "promote",
                "detail": (
                    f"Method '{top_method['method']}' has highest avg rating "
                    f"({top_method['avg_rating']}) across {top_method['count']} papers. "
                    "Consider promoting it in accepted_methods ordering."
                ),
            })
            rationale_parts.append(
                f"method '{top_method['method']}' outperforms others"
            )

    # -- Failure pattern analysis ---------------------------------------------
    top_failures = health_report.get("top_failure_types", [])
    if top_failures:
        dominant = top_failures[0]
        total_failures = sum(f["count"] for f in top_failures)
        dominant_share = dominant["count"] / total_failures if total_failures > 0 else 0.0

        if dominant_share > 0.4:
            # Check if this failure type is already in mandatory_checks
            if dominant["type"] not in mandatory_checks:
                changes.append({
                    "field": "mandatory_checks",
                    "action": "add",
                    "detail": (
                        f"Failure type '{dominant['type']}' accounts for "
                        f"{dominant_share:.0%} of all failures ({dominant['count']}/{total_failures}). "
                        "Consider adding a mandatory check for it."
                    ),
                })
                rationale_parts.append(
                    f"dominant failure type '{dominant['type']}' not in mandatory_checks"
                )

    # -- Reliability-driven suggestions ---------------------------------------
    reliability = health_report.get("reliability_scores", {})
    for metric_type, avg_val in reliability.items():
        if avg_val < 0.5:
            changes.append({
                "field": "fatal_failures",
                "action": "tighten",
                "detail": (
                    f"Reliability metric '{metric_type}' averages {avg_val:.2f}, "
                    "well below 0.5. Consider tightening fatal_failures criteria "
                    "to catch these earlier."
                ),
            })
            rationale_parts.append(f"low reliability on '{metric_type}'")

    # -- Create experiment ----------------------------------------------------
    rationale = (
        "; ".join(rationale_parts)
        if rationale_parts
        else "No significant config changes indicated by current data."
    )

    config_snapshot = {
        "venue_ladder": venue_ladder,
        "accepted_methods": accepted_methods,
        "mandatory_checks": mandatory_checks,
        "health_report_summary": {
            "health_score": health_report.get("health_score"),
            "acceptance_rate": health_report.get("acceptance_rate"),
            "failure_rate": health_report.get("failure_rate"),
        },
    }

    experiment = await create_experiment(
        session,
        tier="2a",
        name=f"family_config_optimization_{family_id}",
        family_id=family_id,
        config_snapshot=config_snapshot,
    )

    logger.info(
        "Proposed %d config changes for family %s (experiment %s)",
        len(changes), family_id, experiment.id,
    )

    return {
        "experiment_id": experiment.id,
        "changes": changes,
        "rationale": rationale,
    }


async def get_all_family_health(session: AsyncSession) -> list[dict]:
    """Get health summary for all active families."""
    families_result = await session.execute(
        select(PaperFamily.id).where(PaperFamily.active.is_(True))
    )
    family_ids = [row[0] for row in families_result.all()]

    results: list[dict] = []
    for fid in family_ids:
        report = await compute_family_health(session, fid)
        results.append(report)

    return results
