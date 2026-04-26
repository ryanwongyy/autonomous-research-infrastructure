"""Tier 4b: Cross-cohort comparison to identify highest-impact improvement targets."""

from __future__ import annotations

import logging

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohort_tag import CohortTag
from app.models.failure_record import FailureRecord
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating
from app.models.review import Review
from app.models.rsi_experiment import RSIExperiment
from app.models.submission_outcome import SubmissionOutcome

logger = logging.getLogger(__name__)

# Metric importance weights for ranking improvement targets
_METRIC_WEIGHTS = {
    "acceptance_rate": 1.0,
    "first_pass_rate": 0.8,
    "failure_rate": 0.9,
    "avg_mu": 0.6,
    "avg_conservative": 0.7,
}

# Tier display labels for improvement target names
_TIER_LABELS = {
    "1a": "tier1a.drafter",
    "1b": "tier1b.reviewer",
    "1c": "tier1c.corrector",
    "2a": "tier2a.family_config",
    "2b": "tier2b.tournament",
    "2c": "tier2c.reliability",
    "3a": "tier3a.prompt_registry",
    "3b": "tier3b.role_prompt",
    "3c": "tier3c.gate_tuning",
    "4a": "tier4a.taxonomy",
    "4b": "tier4b.improvement",
    "4c": "tier4c.meta_pipeline",
}


async def compute_cohort_deltas(session: AsyncSession) -> dict:
    """Compare consecutive cohorts to find metric trends.

    Queries CohortTag grouped by cohort_id, computes aggregate metrics
    for each cohort from linked papers, and calculates deltas between
    consecutive cohorts.

    Returns dict with cohorts list, deltas list, and overall trend.
    """
    # Get cohorts ordered by earliest created_at
    cohort_order_result = await session.execute(
        select(
            CohortTag.cohort_id,
            func.min(CohortTag.created_at).label("first_created"),
            func.count().label("paper_count"),
        )
        .group_by(CohortTag.cohort_id)
        .order_by(func.min(CohortTag.created_at))
    )
    cohort_rows = cohort_order_result.all()

    if not cohort_rows:
        logger.info("No cohort tags found; returning empty deltas")
        return {"cohorts": [], "deltas": [], "trend": "stable"}

    cohorts: list[dict] = []

    for row in cohort_rows:
        cohort_id = row.cohort_id
        paper_count = row.paper_count

        # Get paper IDs in this cohort
        paper_ids_result = await session.execute(
            select(CohortTag.paper_id).where(CohortTag.cohort_id == cohort_id)
        )
        paper_ids = [r[0] for r in paper_ids_result.all()]

        if not paper_ids:
            cohorts.append({
                "cohort_id": cohort_id,
                "paper_count": 0,
                "avg_mu": 0.0,
                "avg_conservative": 0.0,
                "failure_rate": 0.0,
                "acceptance_rate": 0.0,
                "first_pass_rate": 0.0,
            })
            continue

        # Average mu and conservative_rating from ratings
        rating_result = await session.execute(
            select(
                func.avg(Rating.mu).label("avg_mu"),
                func.avg(Rating.conservative_rating).label("avg_cons"),
            ).where(Rating.paper_id.in_(paper_ids))
        )
        rating_row = rating_result.one()
        avg_mu = float(rating_row.avg_mu) if rating_row.avg_mu is not None else 0.0
        avg_cons = float(rating_row.avg_cons) if rating_row.avg_cons is not None else 0.0

        # Failure rate: failures / papers
        failure_count_result = await session.execute(
            select(func.count()).select_from(FailureRecord).where(
                FailureRecord.paper_id.in_(paper_ids)
            )
        )
        failure_count = failure_count_result.scalar() or 0
        failure_rate = failure_count / paper_count if paper_count > 0 else 0.0

        # Acceptance rate from submission outcomes
        outcome_result = await session.execute(
            select(
                func.count().label("total"),
                func.sum(
                    case((SubmissionOutcome.decision == "accepted", 1), else_=0)
                ).label("accepted"),
            ).where(SubmissionOutcome.paper_id.in_(paper_ids))
        )
        outcome_row = outcome_result.one()
        total_subs = outcome_row.total or 0
        accepted_subs = int(outcome_row.accepted or 0)
        acceptance_rate = accepted_subs / total_subs if total_subs > 0 else 0.0

        # First-pass rate: fraction of papers whose first L1 review passed
        first_pass_result = await session.execute(
            select(
                Review.paper_id,
                Review.verdict,
            ).where(
                Review.paper_id.in_(paper_ids),
                Review.stage == "l1_structural",
                Review.iteration == 1,
            )
        )
        first_reviews = first_pass_result.all()
        if first_reviews:
            passed = sum(1 for r in first_reviews if r.verdict == "pass")
            first_pass_rate = passed / len(first_reviews)
        else:
            first_pass_rate = 0.0

        cohorts.append({
            "cohort_id": cohort_id,
            "paper_count": paper_count,
            "avg_mu": round(avg_mu, 4),
            "avg_conservative": round(avg_cons, 4),
            "failure_rate": round(failure_rate, 4),
            "acceptance_rate": round(acceptance_rate, 4),
            "first_pass_rate": round(first_pass_rate, 4),
        })

    # Compute deltas between consecutive cohorts
    deltas: list[dict] = []
    for i in range(1, len(cohorts)):
        prev = cohorts[i - 1]
        curr = cohorts[i]
        deltas.append({
            "from_cohort": prev["cohort_id"],
            "to_cohort": curr["cohort_id"],
            "mu_delta": round(curr["avg_mu"] - prev["avg_mu"], 4),
            "conservative_delta": round(
                curr["avg_conservative"] - prev["avg_conservative"], 4
            ),
            "failure_rate_delta": round(
                curr["failure_rate"] - prev["failure_rate"], 4
            ),
            "acceptance_rate_delta": round(
                curr["acceptance_rate"] - prev["acceptance_rate"], 4
            ),
            "first_pass_rate_delta": round(
                curr["first_pass_rate"] - prev["first_pass_rate"], 4
            ),
        })

    # Determine overall trend from the most recent delta
    if deltas:
        latest = deltas[-1]
        # Positive signals: mu up, conservative up, failure down, acceptance up
        score = (
            (1 if latest["mu_delta"] > 0 else -1 if latest["mu_delta"] < 0 else 0)
            + (1 if latest["conservative_delta"] > 0 else -1 if latest["conservative_delta"] < 0 else 0)
            + (-1 if latest["failure_rate_delta"] > 0 else 1 if latest["failure_rate_delta"] < 0 else 0)
            + (1 if latest["acceptance_rate_delta"] > 0 else -1 if latest["acceptance_rate_delta"] < 0 else 0)
            + (1 if latest["first_pass_rate_delta"] > 0 else -1 if latest["first_pass_rate_delta"] < 0 else 0)
        )
        if score >= 2:
            trend = "improving"
        elif score <= -2:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    logger.info(
        "Computed cohort deltas: %d cohorts, %d deltas, trend=%s",
        len(cohorts), len(deltas), trend,
    )

    return {"cohorts": cohorts, "deltas": deltas, "trend": trend}


async def identify_improvement_targets(
    session: AsyncSession,
) -> list[dict]:
    """Rank improvement targets by expected impact.

    Examines which RSI tier has the most room for improvement, where the
    biggest cohort-over-cohort regressions are, and which families are
    underperforming.

    Returns top 10 targets sorted by expected_impact descending.
    """
    targets: list[dict] = []

    # 1. Cohort-based regressions
    cohort_data = await compute_cohort_deltas(session)
    deltas = cohort_data.get("deltas", [])

    if deltas:
        latest = deltas[-1]
        metric_fields = {
            "acceptance_rate": ("acceptance_rate_delta", False),
            "first_pass_rate": ("first_pass_rate_delta", False),
            "failure_rate": ("failure_rate_delta", True),  # inverted: positive = bad
            "avg_mu": ("mu_delta", False),
            "avg_conservative": ("conservative_delta", False),
        }

        for metric_name, (delta_key, inverted) in metric_fields.items():
            delta_val = latest.get(delta_key, 0.0)
            # For failure_rate, a positive delta is a regression
            regression = delta_val if inverted else -delta_val

            if regression > 0:
                weight = _METRIC_WEIGHTS.get(metric_name, 0.5)
                # Find the latest cohort's actual value
                latest_cohort = cohort_data["cohorts"][-1] if cohort_data["cohorts"] else {}
                current_val = latest_cohort.get(metric_name, 0.0)

                # Target value: reverse the regression
                if inverted:
                    target_val = current_val - regression
                else:
                    target_val = current_val + abs(delta_val)

                paper_volume = latest_cohort.get("paper_count", 1)
                # Expected impact scaled by regression magnitude, volume, and weight
                expected_impact = min(
                    1.0,
                    abs(regression) * weight * min(paper_volume / 10.0, 1.0),
                )

                targets.append({
                    "target": f"cohort_regression.{metric_name}",
                    "expected_impact": round(expected_impact, 4),
                    "rationale": (
                        f"{metric_name} regressed by {delta_val:+.4f} from "
                        f"{latest['from_cohort']} to {latest['to_cohort']}"
                    ),
                    "metric_targeted": metric_name,
                    "current_value": round(current_val, 4),
                    "target_value": round(target_val, 4),
                })

    # 2. Per-tier experiment success rates
    tier_stats_result = await session.execute(
        select(
            RSIExperiment.tier,
            func.count().label("total"),
            func.sum(
                case((RSIExperiment.status == "rolled_back", 1), else_=0)
            ).label("rolled_back"),
            func.sum(
                case((RSIExperiment.status == "active", 1), else_=0)
            ).label("promoted"),
        ).group_by(RSIExperiment.tier)
    )
    tier_rows = tier_stats_result.all()

    for row in tier_rows:
        total = row.total or 0
        rolled_back = int(row.rolled_back or 0)
        promoted = int(row.promoted or 0)

        if total == 0:
            continue

        rollback_rate = rolled_back / total
        promotion_rate = promoted / total

        # High rollback rate signals a tier needs improvement
        if rollback_rate > 0.3:
            tier_label = _TIER_LABELS.get(row.tier, f"tier{row.tier}")
            targets.append({
                "target": tier_label,
                "expected_impact": round(
                    min(1.0, rollback_rate * 0.8), 4
                ),
                "rationale": (
                    f"Tier {row.tier} has {rollback_rate:.0%} rollback rate "
                    f"({rolled_back}/{total} experiments)"
                ),
                "metric_targeted": "experiment_success_rate",
                "current_value": round(promotion_rate, 4),
                "target_value": round(min(1.0, promotion_rate + 0.2), 4),
            })

    # 3. Underperforming families
    families_result = await session.execute(
        select(PaperFamily.id, PaperFamily.short_name).where(
            PaperFamily.active.is_(True)
        )
    )
    families = families_result.all()

    for fam_id, short_name in families:
        # Get paper count and failure rate for this family
        paper_count_result = await session.execute(
            select(func.count()).select_from(Paper).where(
                Paper.family_id == fam_id
            )
        )
        paper_count = paper_count_result.scalar() or 0
        if paper_count == 0:
            continue

        failure_count_result = await session.execute(
            select(func.count()).select_from(FailureRecord).where(
                FailureRecord.family_id == fam_id
            )
        )
        failure_count = failure_count_result.scalar() or 0
        family_failure_rate = failure_count / paper_count

        # Average rating
        rating_result = await session.execute(
            select(func.avg(Rating.conservative_rating)).where(
                Rating.family_id == fam_id
            )
        )
        avg_rating = rating_result.scalar()
        avg_rating_val = float(avg_rating) if avg_rating is not None else 0.0

        # Flag families with high failure rate or low rating
        if family_failure_rate > 0.5:
            impact = min(
                1.0,
                family_failure_rate * 0.7 * min(paper_count / 5.0, 1.0),
            )
            targets.append({
                "target": f"family.{fam_id}.{short_name}",
                "expected_impact": round(impact, 4),
                "rationale": (
                    f"Family {short_name} ({fam_id}) has {family_failure_rate:.0%} "
                    f"failure rate across {paper_count} papers"
                ),
                "metric_targeted": "failure_rate",
                "current_value": round(family_failure_rate, 4),
                "target_value": round(max(0.0, family_failure_rate - 0.2), 4),
            })

        # Normalized rating: conservative_rating in [-25, 25] -> [0, 1]
        norm_rating = (avg_rating_val + 25.0) / 50.0
        if norm_rating < 0.3 and paper_count >= 3:
            impact = min(1.0, (0.3 - norm_rating) * 2.0)
            targets.append({
                "target": f"family.{fam_id}.{short_name}.rating",
                "expected_impact": round(impact, 4),
                "rationale": (
                    f"Family {short_name} ({fam_id}) has low avg conservative "
                    f"rating ({avg_rating_val:.2f}) across {paper_count} papers"
                ),
                "metric_targeted": "avg_conservative_rating",
                "current_value": round(avg_rating_val, 4),
                "target_value": round(avg_rating_val + 5.0, 4),
            })

    # Sort by expected_impact descending, return top 10
    targets.sort(key=lambda t: t["expected_impact"], reverse=True)
    targets = targets[:10]

    logger.info("Identified %d improvement targets", len(targets))
    return targets


async def generate_improvement_summary(session: AsyncSession) -> dict:
    """Generate a human-readable improvement summary.

    Returns dict with overall trajectory, top 3 priorities, active experiments
    by tier, and actionable recommendations.
    """
    # Overall trajectory from cohort deltas
    cohort_data = await compute_cohort_deltas(session)
    trajectory = cohort_data.get("trend", "stable")

    # Top priorities from improvement targets
    targets = await identify_improvement_targets(session)
    top_3 = targets[:3]

    # Active experiments by tier
    active_result = await session.execute(
        select(
            RSIExperiment.tier,
            func.count().label("cnt"),
        )
        .where(RSIExperiment.status.in_(["proposed", "active", "shadow", "a_b_testing"]))
        .group_by(RSIExperiment.tier)
    )
    experiments_by_tier: dict[str, int] = {
        row.tier: row.cnt for row in active_result.all()
    }

    # Generate recommendations
    recommendations: list[str] = []

    if trajectory == "declining":
        recommendations.append(
            "System quality is declining. Prioritize rollback reviews "
            "for recently promoted experiments."
        )
    elif trajectory == "stable":
        recommendations.append(
            "System quality is stable. Consider running more experiments "
            "to push metrics upward."
        )
    else:
        recommendations.append(
            "System quality is improving. Continue current experiment cadence."
        )

    for target in top_3:
        recommendations.append(
            f"Address '{target['target']}': {target['rationale']}. "
            f"Target {target['metric_targeted']} from "
            f"{target['current_value']:.4f} to {target['target_value']:.4f}."
        )

    # Check for tier gaps (tiers with no active experiments)
    all_tiers = sorted(_TIER_LABELS.keys())
    idle_tiers = [t for t in all_tiers if t not in experiments_by_tier]
    if idle_tiers:
        tier_names = ", ".join(
            _TIER_LABELS.get(t, t) for t in idle_tiers[:3]
        )
        recommendations.append(
            f"Tiers with no active experiments: {tier_names}. "
            "Consider initiating experiments to cover these areas."
        )

    logger.info(
        "Generated improvement summary: trajectory=%s, %d priorities, %d recommendations",
        trajectory, len(top_3), len(recommendations),
    )

    return {
        "overall_trajectory": trajectory,
        "top_3_priorities": top_3,
        "active_experiments_by_tier": experiments_by_tier,
        "recommendations": recommendations,
    }
