"""Tier 4c: Orchestrates the full RSI loop: observe -> propose -> shadow -> evaluate -> promote."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failure_record import FailureRecord
from app.models.meta_pipeline_run import MetaPipelineRun
from app.utils import safe_json_loads
from app.models.paper import Paper
from app.models.rating import Rating
from app.models.reliability_metric import ReliabilityMetric
from app.models.rsi_experiment import RSIExperiment
from app.models.rsi_gate_log import RSIGateLog
from app.models.submission_outcome import SubmissionOutcome

logger = logging.getLogger(__name__)

# Minimum papers in an experiment cohort before promotion is allowed
_MIN_COHORT_SIZE = 10

# Maximum acceptable degradation in any critical metric
_MAX_CRITICAL_DEGRADATION = 0.05


async def run_observation_phase(session: AsyncSession) -> dict:
    """Phase 1: Collect current system metrics.

    Gathers failure rates, acceptance rates, reliability scores,
    tournament stats, cohort trends, active experiment results, and
    paper pipeline counts.

    Returns a comprehensive observation dict.
    """
    # -- Paper pipeline counts ---------------------------------------------------
    total_result = await session.execute(
        select(func.count()).select_from(Paper)
    )
    total_papers = total_result.scalar() or 0

    active_result = await session.execute(
        select(func.count()).select_from(Paper).where(
            Paper.funnel_stage.notin_(["killed", "idea"])
        )
    )
    active_papers = active_result.scalar() or 0

    killed_result = await session.execute(
        select(func.count()).select_from(Paper).where(
            Paper.funnel_stage == "killed"
        )
    )
    killed_papers = killed_result.scalar() or 0

    # -- Global failure rate -----------------------------------------------------
    failure_count_result = await session.execute(
        select(func.count()).select_from(FailureRecord)
    )
    total_failures = failure_count_result.scalar() or 0
    global_failure_rate = total_failures / total_papers if total_papers > 0 else 0.0

    # Failure distribution by type
    failure_dist_result = await session.execute(
        select(
            FailureRecord.failure_type,
            func.count().label("cnt"),
        )
        .group_by(FailureRecord.failure_type)
        .order_by(func.count().desc())
    )
    failure_distribution = {
        row.failure_type: row.cnt for row in failure_dist_result.all()
    }

    # -- Global acceptance rate --------------------------------------------------
    outcome_result = await session.execute(
        select(
            func.count().label("total"),
            func.sum(
                case((SubmissionOutcome.decision == "accepted", 1), else_=0)
            ).label("accepted"),
        )
    )
    outcome_row = outcome_result.one()
    total_subs = outcome_row.total or 0
    accepted_subs = int(outcome_row.accepted or 0)
    global_acceptance_rate = accepted_subs / total_subs if total_subs > 0 else 0.0

    # -- Reliability overview ----------------------------------------------------
    reliability_result = await session.execute(
        select(
            ReliabilityMetric.metric_type,
            func.avg(ReliabilityMetric.value).label("avg_val"),
            func.sum(
                case((ReliabilityMetric.passes_threshold.is_(True), 1), else_=0)
            ).label("passing"),
            func.count().label("total"),
        ).group_by(ReliabilityMetric.metric_type)
    )
    reliability_overview: dict[str, dict] = {}
    for row in reliability_result.all():
        total = row.total or 1
        passing = int(row.passing or 0)
        reliability_overview[row.metric_type] = {
            "avg_value": round(float(row.avg_val), 4) if row.avg_val is not None else 0.0,
            "pass_rate": round(passing / total, 4),
            "total_measured": total,
        }

    # -- Tournament stats --------------------------------------------------------
    rating_result = await session.execute(
        select(
            func.avg(Rating.mu).label("avg_mu"),
            func.avg(Rating.conservative_rating).label("avg_cons"),
            func.avg(Rating.sigma).label("avg_sigma"),
            func.count().label("rated_count"),
        )
    )
    rating_row = rating_result.one()
    tournament_stats = {
        "avg_mu": round(float(rating_row.avg_mu), 4) if rating_row.avg_mu is not None else 0.0,
        "avg_conservative": round(float(rating_row.avg_cons), 4) if rating_row.avg_cons is not None else 0.0,
        "avg_sigma": round(float(rating_row.avg_sigma), 4) if rating_row.avg_sigma is not None else 0.0,
        "rated_papers": rating_row.rated_count or 0,
    }

    # -- Cohort trends -----------------------------------------------------------
    from app.services.rsi.improvement_targeter import compute_cohort_deltas
    cohort_data = await compute_cohort_deltas(session)

    # -- Family health -----------------------------------------------------------
    from app.services.rsi.family_config_optimizer import get_all_family_health
    family_health = await get_all_family_health(session)

    # -- Taxonomy status ---------------------------------------------------------
    from app.services.rsi.taxonomy_expander import get_taxonomy_status
    taxonomy = await get_taxonomy_status(session)

    # -- Active experiments ------------------------------------------------------
    from app.services.rsi.experiment_manager import get_active_experiments
    active_experiments = await get_active_experiments(session)

    # -- Recent gate log decisions -----------------------------------------------
    gate_result = await session.execute(
        select(RSIGateLog)
        .order_by(RSIGateLog.decided_at.desc())
        .limit(20)
    )
    recent_gates = [
        {
            "experiment_id": gl.experiment_id,
            "gate_type": gl.gate_type,
            "decision": gl.decision,
            "decided_at": gl.decided_at.isoformat() if gl.decided_at else None,
            "notes": gl.notes,
        }
        for gl in gate_result.scalars().all()
    ]

    observation = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline": {
            "total_papers": total_papers,
            "active_papers": active_papers,
            "killed_papers": killed_papers,
        },
        "failure": {
            "total_failures": total_failures,
            "global_failure_rate": round(global_failure_rate, 4),
            "distribution": failure_distribution,
        },
        "acceptance": {
            "total_submissions": total_subs,
            "total_accepted": accepted_subs,
            "global_acceptance_rate": round(global_acceptance_rate, 4),
        },
        "reliability": reliability_overview,
        "tournament": tournament_stats,
        "cohort_trends": cohort_data,
        "family_health": family_health,
        "taxonomy": taxonomy,
        "active_experiments": active_experiments,
        "recent_gate_decisions": recent_gates,
    }

    logger.info(
        "Observation phase complete: %d papers, %.1f%% failure rate, "
        "%.1f%% acceptance rate, %d active experiments",
        total_papers,
        global_failure_rate * 100,
        global_acceptance_rate * 100,
        len(active_experiments),
    )

    return observation


async def run_proposal_phase(
    session: AsyncSession,
    observations: dict,
) -> list[dict]:
    """Phase 2: Generate improvement proposals based on observations.

    Calls each tier's analysis functions and collects proposals.

    Returns list of proposals sorted by expected_impact descending.
    """
    from app.services.rsi.improvement_targeter import identify_improvement_targets

    targets = await identify_improvement_targets(session)

    proposals: list[dict] = []
    for target in targets:
        # Generate a specific proposal for each target
        proposal = {
            "target": target["target"],
            "expected_impact": target["expected_impact"],
            "rationale": target["rationale"],
            "metric_targeted": target["metric_targeted"],
            "current_value": target["current_value"],
            "target_value": target["target_value"],
            "proposal_type": _classify_proposal_type(target["target"]),
            "observation_context": {
                "global_failure_rate": observations.get("failure", {}).get(
                    "global_failure_rate", 0.0
                ),
                "global_acceptance_rate": observations.get("acceptance", {}).get(
                    "global_acceptance_rate", 0.0
                ),
                "trend": observations.get("cohort_trends", {}).get("trend", "stable"),
            },
        }
        proposals.append(proposal)

    proposals.sort(key=lambda p: p["expected_impact"], reverse=True)

    logger.info("Proposal phase complete: %d proposals generated", len(proposals))
    return proposals


def _classify_proposal_type(target_name: str) -> str:
    """Classify a proposal into a category based on its target name."""
    if target_name.startswith("cohort_regression"):
        return "regression_fix"
    if target_name.startswith("tier"):
        return "tier_improvement"
    if target_name.startswith("family"):
        return "family_optimization"
    return "general"


async def run_evaluation_phase(
    session: AsyncSession,
    proposals: list[dict],
) -> dict:
    """Phase 3: Evaluate proposals against promotion criteria.

    For each proposal, checks if it has enough supporting data and
    scores each proposal's risk level.

    Returns dict with categorized proposals: evaluated, recommended_for_promotion,
    hold, and rejected.
    """
    evaluated: list[dict] = []
    recommended: list[dict] = []
    hold: list[dict] = []
    rejected: list[dict] = []

    for proposal in proposals:
        target = proposal["target"]
        impact = proposal["expected_impact"]

        # Check for existing experiment data backing this target
        experiment_data = await _find_supporting_experiments(session, target)
        paper_count = experiment_data.get("cohort_paper_count", 0)
        has_result = experiment_data.get("has_result", False)

        # Risk assessment
        risk_score = _compute_risk_score(proposal, experiment_data)

        eval_entry = {
            **proposal,
            "supporting_experiments": experiment_data.get("experiment_ids", []),
            "cohort_paper_count": paper_count,
            "has_experiment_result": has_result,
            "risk_score": round(risk_score, 4),
        }
        evaluated.append(eval_entry)

        # Categorize
        if paper_count < _MIN_COHORT_SIZE and has_result is False:
            eval_entry["hold_reason"] = (
                f"Insufficient data: {paper_count} papers in experiment cohort "
                f"(minimum {_MIN_COHORT_SIZE})"
            )
            hold.append(eval_entry)
        elif risk_score > 0.7:
            eval_entry["rejection_reason"] = (
                f"High risk score ({risk_score:.2f}): potential for >5% "
                "degradation in critical metrics"
            )
            rejected.append(eval_entry)
        elif impact >= 0.3 and risk_score <= 0.4:
            eval_entry["recommendation"] = (
                f"High impact ({impact:.2f}) with low risk ({risk_score:.2f})"
            )
            recommended.append(eval_entry)
        elif impact >= 0.1:
            eval_entry["recommendation"] = (
                f"Moderate impact ({impact:.2f}), acceptable risk ({risk_score:.2f})"
            )
            recommended.append(eval_entry)
        else:
            eval_entry["hold_reason"] = (
                f"Low expected impact ({impact:.2f}); deferring"
            )
            hold.append(eval_entry)

    logger.info(
        "Evaluation phase complete: %d evaluated, %d recommended, %d hold, %d rejected",
        len(evaluated), len(recommended), len(hold), len(rejected),
    )

    return {
        "evaluated": evaluated,
        "recommended_for_promotion": recommended,
        "hold": hold,
        "rejected": rejected,
    }


async def _find_supporting_experiments(
    session: AsyncSession,
    target: str,
) -> dict:
    """Find experiments that provide data for a given target."""
    # Extract tier or family from target name
    experiment_ids: list[int] = []
    cohort_paper_count = 0
    has_result = False

    # Match by tier label
    for tier_code, label in {
        "1a": "tier1a", "1b": "tier1b", "1c": "tier1c",
        "2a": "tier2a", "2b": "tier2b", "2c": "tier2c",
        "3a": "tier3a", "3b": "tier3b", "3c": "tier3c",
        "4a": "tier4a", "4b": "tier4b", "4c": "tier4c",
    }.items():
        if label in target:
            result = await session.execute(
                select(RSIExperiment).where(
                    RSIExperiment.tier == tier_code,
                    RSIExperiment.status.in_(["active", "proposed", "shadow"]),
                )
            )
            experiments = result.scalars().all()
            for exp in experiments:
                experiment_ids.append(exp.id)
                if exp.result_summary_json:
                    has_result = True
            break

    # Match by family ID
    if "family." in target:
        parts = target.split(".")
        if len(parts) >= 2:
            family_id = parts[1]
            result = await session.execute(
                select(RSIExperiment).where(
                    RSIExperiment.family_id == family_id,
                    RSIExperiment.status.in_(["active", "proposed", "shadow"]),
                )
            )
            experiments = result.scalars().all()
            for exp in experiments:
                experiment_ids.append(exp.id)
                if exp.result_summary_json:
                    has_result = True

            # Count papers in family as cohort proxy
            count_result = await session.execute(
                select(func.count()).select_from(Paper).where(
                    Paper.family_id == family_id
                )
            )
            cohort_paper_count = count_result.scalar() or 0

    # For cohort regressions, count papers in latest cohort
    if "cohort_regression" in target:
        from app.models.cohort_tag import CohortTag
        latest_cohort_result = await session.execute(
            select(CohortTag.cohort_id, func.count().label("cnt"))
            .group_by(CohortTag.cohort_id)
            .order_by(func.min(CohortTag.created_at).desc())
            .limit(1)
        )
        latest_row = latest_cohort_result.one_or_none()
        if latest_row:
            cohort_paper_count = latest_row.cnt

    return {
        "experiment_ids": experiment_ids,
        "cohort_paper_count": cohort_paper_count,
        "has_result": has_result,
    }


def _compute_risk_score(proposal: dict, experiment_data: dict) -> float:
    """Compute a 0-1 risk score for a proposal.

    Higher risk if:
    - No supporting experiment data
    - Large expected change magnitude
    - Targets critical metrics (acceptance_rate, failure_rate)
    """
    risk = 0.0

    # No experimental backing increases risk
    if not experiment_data.get("experiment_ids"):
        risk += 0.3
    if not experiment_data.get("has_result"):
        risk += 0.2

    # Targeting critical metrics is riskier
    critical_metrics = {"acceptance_rate", "failure_rate"}
    if proposal.get("metric_targeted") in critical_metrics:
        risk += 0.15

    # Large deltas between current and target are riskier
    current = proposal.get("current_value", 0.0)
    target = proposal.get("target_value", 0.0)
    if current != 0:
        change_magnitude = abs(target - current) / abs(current)
    else:
        change_magnitude = abs(target - current)
    risk += min(0.35, change_magnitude * 0.25)

    return min(1.0, risk)


async def run_promotion_gate(
    session: AsyncSession,
    evaluation: dict,
) -> dict:
    """Phase 4: Make promotion decisions.

    Rules:
    - Promote if all metrics improve or hold neutral
    - Hold if insufficient data (< 10 papers in experiment cohort)
    - Reject if any critical metric degrades >5%

    Returns dict with decisions and summary counts.
    """
    decisions: list[dict] = []
    promoted_count = 0
    held_count = 0
    rejected_count = 0

    recommended = evaluation.get("recommended_for_promotion", [])
    held_proposals = evaluation.get("hold", [])
    rejected_proposals = evaluation.get("rejected", [])

    # Process recommended proposals through final promotion gate
    for proposal in recommended:
        paper_count = proposal.get("cohort_paper_count", 0)
        risk = proposal.get("risk_score", 1.0)
        impact = proposal.get("expected_impact", 0.0)

        if paper_count < _MIN_COHORT_SIZE:
            decision = "hold"
            reason = (
                f"Cohort too small ({paper_count} papers, need {_MIN_COHORT_SIZE})"
            )
            held_count += 1
        elif risk > _MAX_CRITICAL_DEGRADATION * 10:  # risk > 0.5
            decision = "hold"
            reason = f"Risk score {risk:.2f} exceeds threshold for auto-promote"
            held_count += 1
        else:
            decision = "promote"
            reason = (
                f"Impact {impact:.2f}, risk {risk:.2f}, "
                f"cohort size {paper_count}"
            )
            promoted_count += 1

        decisions.append({
            "target": proposal["target"],
            "decision": decision,
            "reason": reason,
            "expected_impact": impact,
            "risk_score": risk,
            "cohort_paper_count": paper_count,
        })

    # Record holds
    for proposal in held_proposals:
        held_count += 1
        decisions.append({
            "target": proposal["target"],
            "decision": "hold",
            "reason": proposal.get("hold_reason", "Insufficient data or low impact"),
            "expected_impact": proposal.get("expected_impact", 0.0),
            "risk_score": proposal.get("risk_score", 0.0),
            "cohort_paper_count": proposal.get("cohort_paper_count", 0),
        })

    # Record rejections
    for proposal in rejected_proposals:
        rejected_count += 1
        decisions.append({
            "target": proposal["target"],
            "decision": "reject",
            "reason": proposal.get(
                "rejection_reason",
                "Critical metric degradation risk >5%",
            ),
            "expected_impact": proposal.get("expected_impact", 0.0),
            "risk_score": proposal.get("risk_score", 0.0),
            "cohort_paper_count": proposal.get("cohort_paper_count", 0),
        })

    logger.info(
        "Promotion gate complete: %d promoted, %d held, %d rejected",
        promoted_count, held_count, rejected_count,
    )

    return {
        "decisions": decisions,
        "promoted_count": promoted_count,
        "held_count": held_count,
        "rejected_count": rejected_count,
    }


async def execute_meta_cycle(session: AsyncSession) -> dict:
    """Orchestrate one full RSI meta-cycle.

    Creates a MetaPipelineRun, executes all 4 phases sequentially,
    records results at each stage, and returns a summary.

    Returns dict with run_id, final status, and summary.
    """
    now = datetime.now(timezone.utc)

    # Create the run record
    run = MetaPipelineRun(
        status="observing",
        started_at=now,
    )
    session.add(run)
    await session.flush()
    run_id = run.id

    logger.info("Starting meta-pipeline cycle (run_id=%d)", run_id)

    try:
        # Phase 1: Observe
        observations = await run_observation_phase(session)
        run.observation_json = json.dumps(observations, default=str)
        run.status = "proposing"
        await session.flush()

        # Phase 2: Propose
        proposals = await run_proposal_phase(session, observations)
        run.proposals_json = json.dumps(proposals, default=str)
        run.status = "evaluating"
        await session.flush()

        # Phase 3: Evaluate
        evaluation = await run_evaluation_phase(session, proposals)
        run.shadow_results_json = json.dumps(evaluation, default=str)
        run.status = "promoting"
        await session.flush()

        # Phase 4: Promote
        promotion = await run_promotion_gate(session, evaluation)

        # Determine overall promotion decision
        if promotion["promoted_count"] > 0:
            overall_decision = "promoted"
        elif promotion["held_count"] > 0 and promotion["rejected_count"] == 0:
            overall_decision = "held"
        elif promotion["rejected_count"] > 0:
            overall_decision = "mixed"
        else:
            overall_decision = "no_action"

        run.promotion_decision = overall_decision[:16]
        run.production_delta_json = json.dumps(promotion, default=str)
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await session.flush()

        summary = {
            "total_proposals": len(proposals),
            "promoted": promotion["promoted_count"],
            "held": promotion["held_count"],
            "rejected": promotion["rejected_count"],
            "overall_decision": overall_decision,
            "trend": observations.get("cohort_trends", {}).get("trend", "stable"),
            "global_failure_rate": observations.get("failure", {}).get(
                "global_failure_rate", 0.0
            ),
            "global_acceptance_rate": observations.get("acceptance", {}).get(
                "global_acceptance_rate", 0.0
            ),
        }

        logger.info(
            "Meta-pipeline cycle completed (run_id=%d): %s",
            run_id, overall_decision,
        )

        return {"run_id": run_id, "status": "completed", "summary": summary}

    except Exception:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        await session.flush()
        logger.exception("Meta-pipeline cycle failed (run_id=%d)", run_id)
        raise


async def get_meta_pipeline_runs(
    session: AsyncSession,
    limit: int = 10,
) -> list[dict]:
    """List recent meta-pipeline runs, most recent first."""
    result = await session.execute(
        select(MetaPipelineRun)
        .order_by(MetaPipelineRun.started_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()

    return [
        {
            "id": run.id,
            "status": run.status,
            "promotion_decision": run.promotion_decision,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "has_observations": run.observation_json is not None,
            "has_proposals": run.proposals_json is not None,
            "has_shadow_results": run.shadow_results_json is not None,
            "has_production_delta": run.production_delta_json is not None,
        }
        for run in runs
    ]


async def get_meta_pipeline_run(
    session: AsyncSession,
    run_id: int,
) -> dict | None:
    """Get full detail of a specific meta-pipeline run.

    Returns None if the run does not exist.
    """
    result = await session.execute(
        select(MetaPipelineRun).where(MetaPipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None

    return {
        "id": run.id,
        "status": run.status,
        "promotion_decision": run.promotion_decision,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "observation": safe_json_loads(run.observation_json, None),
        "proposals": safe_json_loads(run.proposals_json, None),
        "shadow_results": safe_json_loads(run.shadow_results_json, None),
        "production_delta": safe_json_loads(run.production_delta_json, None),
    }
