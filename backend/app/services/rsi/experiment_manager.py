"""Manages RSI experiments lifecycle: creation, activation, evaluation, rollback."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rsi_experiment import RSIExperiment
from app.models.rsi_gate_log import RSIGateLog
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

VALID_TIERS = frozenset(f"{n}{s}" for n in range(1, 5) for s in ("a", "b", "c"))

DEFAULT_DEGRADATION_THRESHOLD = 0.10


async def create_experiment(
    session: AsyncSession,
    tier: str,
    name: str,
    family_id: str | None = None,
    config_snapshot: dict | None = None,
) -> RSIExperiment:
    """Create a new RSI experiment in 'proposed' status."""
    if tier not in VALID_TIERS:
        raise ValueError(f"Invalid tier '{tier}'. Must be one of: {', '.join(sorted(VALID_TIERS))}")

    experiment = RSIExperiment(
        tier=tier,
        name=name,
        status="proposed",
        family_id=family_id,
        created_by="system",
        config_snapshot_json=json.dumps(config_snapshot) if config_snapshot else None,
    )
    session.add(experiment)
    await session.flush()
    logger.info("Created RSI experiment %s (tier=%s, name=%s)", experiment.id, tier, name)
    return experiment


async def activate_experiment(
    session: AsyncSession,
    experiment_id: int,
) -> RSIExperiment:
    """Move experiment from proposed/shadow to active. Sets activated_at."""
    result = await session.execute(select(RSIExperiment).where(RSIExperiment.id == experiment_id))
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise ValueError(f"Experiment {experiment_id} not found")

    allowed_statuses = ("proposed", "shadow", "a_b_testing")
    if experiment.status not in allowed_statuses:
        raise ValueError(
            f"Cannot activate experiment in status '{experiment.status}'. "
            f"Must be one of: {', '.join(allowed_statuses)}"
        )

    experiment.status = "active"
    experiment.activated_at = datetime.now(UTC)

    await _log_gate(
        session,
        experiment_id=experiment.id,
        gate_type="activation",
        decision="activated",
        notes=f"Activated from status '{experiment.status}'",
    )

    logger.info("Activated RSI experiment %s", experiment.id)
    return experiment


async def rollback_experiment(
    session: AsyncSession,
    experiment_id: int,
    reason: str = "",
) -> RSIExperiment:
    """Roll back an active experiment. Sets rolled_back_at."""
    result = await session.execute(select(RSIExperiment).where(RSIExperiment.id == experiment_id))
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise ValueError(f"Experiment {experiment_id} not found")

    experiment.status = "rolled_back"
    experiment.rolled_back_at = datetime.now(UTC)

    await _log_gate(
        session,
        experiment_id=experiment.id,
        gate_type="rollback",
        decision="rolled_back",
        notes=reason or None,
    )

    logger.info("Rolled back RSI experiment %s: %s", experiment.id, reason)
    return experiment


async def evaluate_experiment(
    session: AsyncSession,
    experiment_id: int,
    metrics_before: dict,
    metrics_after: dict,
    thresholds: dict | None = None,
) -> dict:
    """Compare metrics before/after an experiment. Returns evaluation result.

    Default threshold: any metric degradation >10% triggers rollback recommendation.
    Returns {"decision": "promote"|"hold"|"rollback", "details": {...}}
    """
    result = await session.execute(select(RSIExperiment).where(RSIExperiment.id == experiment_id))
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise ValueError(f"Experiment {experiment_id} not found")

    effective_thresholds = thresholds or {}
    details: dict[str, dict] = {}
    any_degraded = False
    all_improved_or_held = True

    for metric_key in set(metrics_before.keys()) | set(metrics_after.keys()):
        before_val = metrics_before.get(metric_key)
        after_val = metrics_after.get(metric_key)

        if before_val is None or after_val is None:
            details[metric_key] = {
                "before": before_val,
                "after": after_val,
                "change": None,
                "status": "missing_data",
            }
            continue

        before_val = float(before_val)
        after_val = float(after_val)

        if before_val != 0:
            change = (after_val - before_val) / abs(before_val)
        else:
            change = 0.0 if after_val == 0 else 1.0

        max_degradation = effective_thresholds.get(metric_key, DEFAULT_DEGRADATION_THRESHOLD)

        if change < -max_degradation:
            status = "degraded"
            any_degraded = True
            all_improved_or_held = False
        elif change < 0:
            status = "slightly_declined"
            all_improved_or_held = False
        elif change == 0:
            status = "held"
        else:
            status = "improved"

        details[metric_key] = {
            "before": before_val,
            "after": after_val,
            "change_pct": round(change * 100, 2),
            "threshold_pct": round(max_degradation * 100, 2),
            "status": status,
        }

    if any_degraded:
        decision = "rollback"
    elif all_improved_or_held:
        decision = "promote"
    else:
        decision = "hold"

    evaluation = {"decision": decision, "details": details}

    experiment.result_summary_json = json.dumps(evaluation)

    await _log_gate(
        session,
        experiment_id=experiment.id,
        gate_type="evaluation",
        decision=decision,
        metric_before=metrics_before,
        metric_after=metrics_after,
        thresholds=effective_thresholds or None,
        notes=f"Evaluation decision: {decision}",
    )

    logger.info("Evaluated RSI experiment %s: decision=%s", experiment.id, decision)
    return evaluation


async def get_active_experiments(
    session: AsyncSession,
    tier: str | None = None,
    family_id: str | None = None,
) -> list[dict]:
    """List active/running experiments with optional filters."""
    excluded_statuses = ("archived", "rolled_back")
    query = select(RSIExperiment).where(RSIExperiment.status.notin_(excluded_statuses))

    if tier is not None:
        query = query.where(RSIExperiment.tier == tier)
    if family_id is not None:
        query = query.where(RSIExperiment.family_id == family_id)

    query = query.order_by(RSIExperiment.created_at.desc())
    result = await session.execute(query)
    experiments = result.scalars().all()

    return [
        {
            "id": exp.id,
            "tier": exp.tier,
            "name": exp.name,
            "status": exp.status,
            "family_id": exp.family_id,
            "created_by": exp.created_by,
            "proposed_at": exp.proposed_at.isoformat() if exp.proposed_at else None,
            "activated_at": exp.activated_at.isoformat() if exp.activated_at else None,
            "config_snapshot": safe_json_loads(exp.config_snapshot_json, None),
            "result_summary": safe_json_loads(exp.result_summary_json, None),
        }
        for exp in experiments
    ]


async def get_experiment(session: AsyncSession, experiment_id: int) -> dict | None:
    """Get single experiment detail."""
    result = await session.execute(select(RSIExperiment).where(RSIExperiment.id == experiment_id))
    exp = result.scalar_one_or_none()
    if exp is None:
        return None

    return {
        "id": exp.id,
        "tier": exp.tier,
        "name": exp.name,
        "status": exp.status,
        "cohort_id": exp.cohort_id,
        "family_id": exp.family_id,
        "created_by": exp.created_by,
        "proposed_at": exp.proposed_at.isoformat() if exp.proposed_at else None,
        "activated_at": exp.activated_at.isoformat() if exp.activated_at else None,
        "rolled_back_at": exp.rolled_back_at.isoformat() if exp.rolled_back_at else None,
        "config_snapshot": safe_json_loads(exp.config_snapshot_json, None),
        "result_summary": safe_json_loads(exp.result_summary_json, None),
        "created_at": exp.created_at.isoformat() if exp.created_at else None,
    }


async def get_rsi_dashboard(session: AsyncSession) -> dict:
    """Aggregate RSI dashboard data: counts by tier, by status, recent gate logs."""
    # Counts by tier
    tier_counts_result = await session.execute(
        select(RSIExperiment.tier, func.count()).group_by(RSIExperiment.tier)
    )
    by_tier = {row[0]: row[1] for row in tier_counts_result.all()}

    # Counts by status
    status_counts_result = await session.execute(
        select(RSIExperiment.status, func.count()).group_by(RSIExperiment.status)
    )
    by_status = {row[0]: row[1] for row in status_counts_result.all()}

    # Recent gate logs (last 20)
    gate_logs_result = await session.execute(
        select(RSIGateLog).order_by(RSIGateLog.decided_at.desc()).limit(20)
    )
    gate_logs = gate_logs_result.scalars().all()

    recent_gates = [
        {
            "id": gl.id,
            "experiment_id": gl.experiment_id,
            "gate_type": gl.gate_type,
            "decision": gl.decision,
            "decided_at": gl.decided_at.isoformat() if gl.decided_at else None,
            "notes": gl.notes,
            "metric_before": safe_json_loads(gl.metric_before_json, None),
            "metric_after": safe_json_loads(gl.metric_after_json, None),
            "thresholds": safe_json_loads(gl.threshold_json, None),
        }
        for gl in gate_logs
    ]

    total_result = await session.execute(select(func.count()).select_from(RSIExperiment))
    total_experiments = total_result.scalar() or 0

    return {
        "total_experiments": total_experiments,
        "by_tier": by_tier,
        "by_status": by_status,
        "recent_gate_logs": recent_gates,
    }


async def _log_gate(
    session: AsyncSession,
    experiment_id: int,
    gate_type: str,
    decision: str,
    metric_before: dict | None = None,
    metric_after: dict | None = None,
    thresholds: dict | None = None,
    notes: str | None = None,
) -> None:
    """Internal: create an RSIGateLog entry."""
    log_entry = RSIGateLog(
        experiment_id=experiment_id,
        gate_type=gate_type,
        decision=decision,
        metric_before_json=json.dumps(metric_before) if metric_before else None,
        metric_after_json=json.dumps(metric_after) if metric_after else None,
        threshold_json=json.dumps(thresholds) if thresholds else None,
        notes=notes,
    )
    session.add(log_entry)
    await session.flush()
