"""Tier 2b: Auto-tunes manifest-drift thresholds based on gate effectiveness."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.drift_threshold_log import DriftThresholdLog
from app.models.failure_record import FailureRecord
from app.models.paper import Paper
from app.services.rsi.experiment_manager import create_experiment

logger = logging.getLogger(__name__)

THRESHOLD_FLOOR = 0.6
THRESHOLD_CEILING = 0.95
THRESHOLD_STEP = 0.05

# Funnel stages considered "past the drift gates"
_POST_GATE_STAGES = frozenset(
    {
        "analyzing",
        "drafting",
        "reviewing",
        "revision",
        "benchmark",
        "candidate",
        "submitted",
        "public",
    }
)

# Detection stages that correspond to drift-gate blocking
_DRIFT_GATE_STAGES = frozenset(
    {
        "l2_provenance",
        "manifest_drift",
        "boundary_enforcer",
    }
)


async def compute_gate_metrics(
    session: AsyncSession,
    family_id: str | None = None,
    days: int = 90,
) -> dict:
    """Compute drift gate effectiveness metrics.

    Measures how well the current threshold separates good from bad papers:
    block rate, downstream failure rate, and blocked-then-succeeded rate.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)

    # -- Total papers that entered the pipeline in the window -----------------
    total_q = select(func.count()).select_from(Paper).where(Paper.created_at >= cutoff)
    if family_id is not None:
        total_q = total_q.where(Paper.family_id == family_id)
    total_result = await session.execute(total_q)
    total_papers: int = total_result.scalar() or 0

    if total_papers == 0:
        return {
            "gate_block_rate": 0.0,
            "downstream_failure_rate": 0.0,
            "blocked_then_succeeded_rate": 0.0,
            "papers_evaluated": 0,
        }

    # -- Papers blocked at drift gates ----------------------------------------
    blocked_q = select(func.count(func.distinct(FailureRecord.paper_id))).where(
        FailureRecord.detection_stage.in_(_DRIFT_GATE_STAGES),
        FailureRecord.created_at >= cutoff,
    )
    if family_id is not None:
        blocked_q = blocked_q.where(FailureRecord.family_id == family_id)
    blocked_result = await session.execute(blocked_q)
    blocked_count: int = blocked_result.scalar() or 0

    gate_block_rate = blocked_count / total_papers

    # -- Papers that passed gates but had downstream failures -----------------
    # Papers currently past the gate stages
    passed_q = (
        select(func.count())
        .select_from(Paper)
        .where(
            Paper.funnel_stage.in_(_POST_GATE_STAGES),
            Paper.created_at >= cutoff,
        )
    )
    if family_id is not None:
        passed_q = passed_q.where(Paper.family_id == family_id)
    passed_result = await session.execute(passed_q)
    passed_count: int = passed_result.scalar() or 0

    # Of those, how many have later failures (detection_stage NOT in drift gate stages)
    if passed_count > 0:
        downstream_fail_q = (
            select(func.count(func.distinct(FailureRecord.paper_id)))
            .join(Paper, Paper.id == FailureRecord.paper_id)
            .where(
                Paper.funnel_stage.in_(_POST_GATE_STAGES),
                Paper.created_at >= cutoff,
                FailureRecord.detection_stage.notin_(_DRIFT_GATE_STAGES),
            )
        )
        if family_id is not None:
            downstream_fail_q = downstream_fail_q.where(FailureRecord.family_id == family_id)
        downstream_fail_result = await session.execute(downstream_fail_q)
        downstream_fail_count: int = downstream_fail_result.scalar() or 0
        downstream_failure_rate = downstream_fail_count / passed_count
    else:
        downstream_failure_rate = 0.0

    # -- Blocked papers that were revised and later succeeded -----------------
    # Papers that had a drift-gate failure AND later reached candidate/submitted/public
    if blocked_count > 0:
        revised_success_q = (
            select(func.count(func.distinct(FailureRecord.paper_id)))
            .join(Paper, Paper.id == FailureRecord.paper_id)
            .where(
                FailureRecord.detection_stage.in_(_DRIFT_GATE_STAGES),
                FailureRecord.created_at >= cutoff,
                Paper.funnel_stage.in_({"candidate", "submitted", "public"}),
            )
        )
        if family_id is not None:
            revised_success_q = revised_success_q.where(FailureRecord.family_id == family_id)
        revised_result = await session.execute(revised_success_q)
        revised_count: int = revised_result.scalar() or 0
        blocked_then_succeeded_rate = revised_count / blocked_count
    else:
        blocked_then_succeeded_rate = 0.0

    return {
        "gate_block_rate": round(gate_block_rate, 4),
        "downstream_failure_rate": round(downstream_failure_rate, 4),
        "blocked_then_succeeded_rate": round(blocked_then_succeeded_rate, 4),
        "papers_evaluated": total_papers,
    }


async def propose_threshold_adjustment(
    session: AsyncSession,
    family_id: str | None = None,
) -> dict:
    """Propose a threshold adjustment based on gate effectiveness metrics.

    Rules:
    - block_rate > 0.3 AND downstream_failure_rate < 0.1 => too strict, decrease
    - block_rate < 0.05 AND downstream_failure_rate > 0.2 => too lenient, increase
    - Otherwise => hold
    - Clamp between THRESHOLD_FLOOR and THRESHOLD_CEILING
    """
    metrics = await compute_gate_metrics(session, family_id=family_id)

    # Determine current threshold: use latest per-family override or global default
    current_threshold = await _get_effective_threshold(session, family_id)

    block_rate = metrics["gate_block_rate"]
    downstream_rate = metrics["downstream_failure_rate"]

    if block_rate > 0.3 and downstream_rate < 0.1:
        direction = "decrease"
        proposed = current_threshold - THRESHOLD_STEP
        rationale = (
            f"Gate is too strict: block rate {block_rate:.1%} > 30% while "
            f"downstream failure rate {downstream_rate:.1%} < 10%. "
            "Lowering threshold to allow more papers through."
        )
    elif block_rate < 0.05 and downstream_rate > 0.2:
        direction = "increase"
        proposed = current_threshold + THRESHOLD_STEP
        rationale = (
            f"Gate is too lenient: block rate {block_rate:.1%} < 5% while "
            f"downstream failure rate {downstream_rate:.1%} > 20%. "
            "Raising threshold to catch more issues early."
        )
    else:
        direction = "hold"
        proposed = current_threshold
        rationale = (
            f"Gate balance is acceptable: block rate {block_rate:.1%}, "
            f"downstream failure rate {downstream_rate:.1%}. No adjustment needed."
        )

    # Clamp
    proposed = round(max(THRESHOLD_FLOOR, min(THRESHOLD_CEILING, proposed)), 4)

    experiment_id: int | None = None
    if direction != "hold":
        experiment = await create_experiment(
            session,
            tier="2b",
            name=f"drift_threshold_{'decrease' if direction == 'decrease' else 'increase'}"
            f"{'_' + family_id if family_id else '_global'}",
            family_id=family_id,
            config_snapshot={
                "current_threshold": current_threshold,
                "proposed_threshold": proposed,
                "metrics": metrics,
            },
        )
        experiment_id = experiment.id

    logger.info(
        "Threshold proposal for family=%s: %s (%.4f -> %.4f)",
        family_id or "global",
        direction,
        current_threshold,
        proposed,
    )

    return {
        "experiment_id": experiment_id,
        "current_threshold": current_threshold,
        "proposed_threshold": proposed,
        "direction": direction,
        "metrics": metrics,
        "rationale": rationale,
    }


async def apply_threshold(
    session: AsyncSession,
    new_threshold: float,
    family_id: str | None = None,
    experiment_id: int | None = None,
) -> dict:
    """Apply a new drift threshold. Records the change in DriftThresholdLog.

    The global ``settings.drift_threshold`` is immutable at runtime; per-family
    overrides are stored in DriftThresholdLog for the boundary_enforcer to query.
    """
    if not (THRESHOLD_FLOOR <= new_threshold <= THRESHOLD_CEILING):
        raise ValueError(
            f"Threshold {new_threshold} out of range [{THRESHOLD_FLOOR}, {THRESHOLD_CEILING}]"
        )

    current_threshold = await _get_effective_threshold(session, family_id)

    # Compute current gate metrics for the log entry
    metrics = await compute_gate_metrics(session, family_id=family_id)

    log_entry = DriftThresholdLog(
        family_id=family_id,
        previous_threshold=current_threshold,
        new_threshold=new_threshold,
        gate_block_rate=metrics["gate_block_rate"],
        downstream_failure_rate=metrics["downstream_failure_rate"],
        experiment_id=experiment_id,
    )
    session.add(log_entry)
    await session.flush()

    logger.info(
        "Applied drift threshold %.4f (was %.4f) for family=%s, log_id=%s",
        new_threshold,
        current_threshold,
        family_id or "global",
        log_entry.id,
    )

    return {
        "id": log_entry.id,
        "family_id": log_entry.family_id,
        "previous_threshold": log_entry.previous_threshold,
        "new_threshold": log_entry.new_threshold,
        "gate_block_rate": log_entry.gate_block_rate,
        "downstream_failure_rate": log_entry.downstream_failure_rate,
        "experiment_id": log_entry.experiment_id,
        "adjusted_at": log_entry.adjusted_at.isoformat() if log_entry.adjusted_at else None,
    }


async def get_threshold_history(
    session: AsyncSession,
    family_id: str | None = None,
) -> list[dict]:
    """Get threshold adjustment history, optionally filtered by family."""
    query = select(DriftThresholdLog).order_by(DriftThresholdLog.adjusted_at.desc())
    if family_id is not None:
        query = query.where(DriftThresholdLog.family_id == family_id)
    else:
        # Include global entries (family_id IS NULL) and all family entries
        pass

    result = await session.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "family_id": log.family_id,
            "previous_threshold": log.previous_threshold,
            "new_threshold": log.new_threshold,
            "gate_block_rate": log.gate_block_rate,
            "downstream_failure_rate": log.downstream_failure_rate,
            "experiment_id": log.experiment_id,
            "adjusted_at": log.adjusted_at.isoformat() if log.adjusted_at else None,
        }
        for log in logs
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_effective_threshold(
    session: AsyncSession,
    family_id: str | None,
) -> float:
    """Return the most recent threshold for a family, falling back to the
    global config default."""
    if family_id is not None:
        latest_result = await session.execute(
            select(DriftThresholdLog.new_threshold)
            .where(DriftThresholdLog.family_id == family_id)
            .order_by(DriftThresholdLog.adjusted_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        if latest is not None:
            return float(latest)

    # Fall back to global override (family_id IS NULL) if one exists
    global_result = await session.execute(
        select(DriftThresholdLog.new_threshold)
        .where(DriftThresholdLog.family_id.is_(None))
        .order_by(DriftThresholdLog.adjusted_at.desc())
        .limit(1)
    )
    global_latest = global_result.scalar_one_or_none()
    if global_latest is not None:
        return float(global_latest)

    return settings.drift_threshold
