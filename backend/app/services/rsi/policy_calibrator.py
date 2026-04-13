"""Tier 1c: Correlates policy-usefulness dimensions with venue outcomes to
calibrate scoring weights."""

from __future__ import annotations

import json
import logging
import math

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.paper import Paper
from app.models.submission_outcome import SubmissionOutcome
from app.utils import safe_json_loads
from app.models.rsi_experiment import RSIExperiment
from app.models.prompt_version import PromptVersion
from app.services.rsi.experiment_manager import create_experiment
from app.services.rsi.prompt_registry import register_prompt, get_active_prompt

logger = logging.getLogger(__name__)

POLICY_DIMENSIONS = [
    "actionability",
    "specificity",
    "evidence_strength",
    "stakeholder_relevance",
    "implementation_feasibility",
]

# Default equal weights.
_DEFAULT_WEIGHT = 1.0 / len(POLICY_DIMENSIONS)

# Minimum sample size before we trust correlation results.
_MIN_SAMPLE_SIZE = 10

# Target type/key used in the prompt registry for weight configuration.
_WEIGHTS_TARGET_TYPE = "policy_weights"
_WEIGHTS_TARGET_KEY = "dimension_weights"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def correlate_dimensions_with_outcomes(
    session: AsyncSession,
    family_id: str | None = None,
) -> dict:
    """Compute correlation between each policy dimension score and venue acceptance.

    Joins Review.policy_scores_json with SubmissionOutcome.decision to
    compute, for each of the 5 dimensions, the average score among accepted
    papers versus rejected papers and a point-biserial-style correlation
    (difference of means normalized by pooled standard deviation).
    """
    # ------------------------------------------------------------------
    # 1. Gather (paper_id, policy_scores, decision) triples.
    # ------------------------------------------------------------------
    query = (
        select(
            Review.paper_id,
            Review.policy_scores_json,
            SubmissionOutcome.decision,
        )
        .join(Paper, Paper.id == Review.paper_id)
        .join(SubmissionOutcome, SubmissionOutcome.paper_id == Review.paper_id)
        .where(
            Review.policy_scores_json.isnot(None),
            SubmissionOutcome.decision.isnot(None),
        )
    )
    if family_id is not None:
        query = query.where(Paper.family_id == family_id)

    # Use the latest review per paper that has policy scores.
    query = query.order_by(Review.paper_id, Review.created_at.desc())

    result = await session.execute(query)
    rows = result.all()

    # De-duplicate: keep only the latest review row per paper.
    seen_papers: set[str] = set()
    samples: list[tuple[dict, bool]] = []  # (scores_dict, is_accepted)
    for paper_id, scores_json, decision in rows:
        if paper_id in seen_papers:
            continue
        seen_papers.add(paper_id)
        scores = safe_json_loads(scores_json, None)
        if not isinstance(scores, dict):
            continue
        is_accepted = decision in ("accepted", "r_and_r")
        samples.append((scores, is_accepted))

    sample_size = len(samples)
    if sample_size < _MIN_SAMPLE_SIZE:
        return {
            "sample_size": sample_size,
            "correlations": {},
            "most_predictive": None,
            "least_predictive": None,
            "warning": (
                f"Insufficient sample size ({sample_size}). "
                f"Need at least {_MIN_SAMPLE_SIZE} papers with both "
                "policy scores and venue decisions."
            ),
        }

    # ------------------------------------------------------------------
    # 2. Per-dimension statistics.
    # ------------------------------------------------------------------
    correlations: dict[str, dict] = {}

    for dim in POLICY_DIMENSIONS:
        accepted_scores: list[float] = []
        rejected_scores: list[float] = []

        for scores, is_accepted in samples:
            val = scores.get(dim)
            if val is None:
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if is_accepted:
                accepted_scores.append(val)
            else:
                rejected_scores.append(val)

        n_acc = len(accepted_scores)
        n_rej = len(rejected_scores)

        avg_accepted = _safe_mean(accepted_scores)
        avg_rejected = _safe_mean(rejected_scores)

        # Point-biserial correlation approximation.
        correlation = _point_biserial(accepted_scores, rejected_scores)

        # Simple significance heuristic: consider significant if we have
        # at least 5 in each group and |r| > 0.15.
        p_significant = (
            n_acc >= 5 and n_rej >= 5 and abs(correlation) > 0.15
        )

        correlations[dim] = {
            "correlation": round(correlation, 4),
            "p_significant": p_significant,
            "avg_accepted": round(avg_accepted, 4),
            "avg_rejected": round(avg_rejected, 4),
            "n_accepted": n_acc,
            "n_rejected": n_rej,
        }

    # Identify most / least predictive dimensions.
    ranked = sorted(
        correlations.items(),
        key=lambda kv: abs(kv[1]["correlation"]),
        reverse=True,
    )
    most_predictive = ranked[0][0] if ranked else None
    least_predictive = ranked[-1][0] if ranked else None

    return {
        "sample_size": sample_size,
        "correlations": correlations,
        "most_predictive": most_predictive,
        "least_predictive": least_predictive,
    }


async def propose_dimension_reweighting(
    session: AsyncSession,
    correlation_analysis: dict,
) -> dict:
    """Propose new weights for the 5 policy dimensions based on predictiveness.

    Dimensions with higher absolute correlation to acceptance receive higher
    weights. Weights are normalized to sum to 1.0.  A minimum floor of 0.05
    is enforced so that no dimension is zeroed out entirely.
    """
    correlations = correlation_analysis.get("correlations", {})
    sample_size = correlation_analysis.get("sample_size", 0)

    current_weights = {dim: _DEFAULT_WEIGHT for dim in POLICY_DIMENSIONS}

    if not correlations or sample_size < _MIN_SAMPLE_SIZE:
        return {
            "experiment_id": None,
            "current_weights": current_weights,
            "proposed_weights": current_weights,
            "rationale": (
                f"Insufficient data (n={sample_size}) to propose reweighting. "
                "Keeping equal weights."
            ),
        }

    # Compute raw weights from absolute correlations.
    raw: dict[str, float] = {}
    for dim in POLICY_DIMENSIONS:
        dim_corr = correlations.get(dim, {})
        raw[dim] = abs(dim_corr.get("correlation", 0.0))

    # Apply floor.
    floor = 0.05
    floored = {dim: max(val, floor) for dim, val in raw.items()}

    # Normalize to sum to 1.0.
    total = sum(floored.values())
    if total == 0:
        proposed_weights = current_weights
    else:
        proposed_weights = {
            dim: round(val / total, 4) for dim, val in floored.items()
        }

    # Build rationale.
    most_pred = correlation_analysis.get("most_predictive", "N/A")
    least_pred = correlation_analysis.get("least_predictive", "N/A")
    rationale = (
        f"Reweighting based on {sample_size} papers with venue outcomes. "
        f"Most predictive dimension: {most_pred} "
        f"(r={correlations.get(most_pred, {}).get('correlation', 'N/A')}). "
        f"Least predictive: {least_pred} "
        f"(r={correlations.get(least_pred, {}).get('correlation', 'N/A')}). "
        f"Weights normalized with floor={floor}."
    )

    # Create experiment.
    experiment = await create_experiment(
        session,
        tier="1c",
        name=f"policy_reweight_n{sample_size}_{most_pred}",
        config_snapshot={
            "sample_size": sample_size,
            "correlations": correlations,
            "current_weights": current_weights,
            "proposed_weights": proposed_weights,
        },
    )

    # Register the new weights as a "prompt" version (the weights config is
    # stored as JSON text, consistent with how the registry versions things).
    weight_text = json.dumps(proposed_weights, indent=2)
    prompt_version = await register_prompt(
        session,
        target_type=_WEIGHTS_TARGET_TYPE,
        target_key=_WEIGHTS_TARGET_KEY,
        prompt_text=weight_text,
        experiment_id=experiment.id,
    )

    logger.info(
        "Tier 1c reweighting proposed (experiment %s): %s",
        experiment.id, rationale,
    )

    return {
        "experiment_id": experiment.id,
        "prompt_version_id": prompt_version.id,
        "current_weights": current_weights,
        "proposed_weights": proposed_weights,
        "rationale": rationale,
    }


async def get_calibration_status(session: AsyncSession) -> dict:
    """Get current calibration state: active weights, last analysis, sample sizes.

    Returns a summary of the current policy dimension weight configuration,
    recent experiments, and the number of papers with policy scores available.
    """
    # Active weights from the registry.
    active_weights_text = await get_active_prompt(
        session, _WEIGHTS_TARGET_TYPE, _WEIGHTS_TARGET_KEY
    )
    default_weights = {dim: _DEFAULT_WEIGHT for dim in POLICY_DIMENSIONS}
    if active_weights_text is not None:
        active_weights = safe_json_loads(active_weights_text, default_weights)
    else:
        active_weights = default_weights

    # Count papers that have policy scores.
    scored_result = await session.execute(
        select(func.count(func.distinct(Review.paper_id))).where(
            Review.policy_scores_json.isnot(None),
        )
    )
    papers_with_scores = scored_result.scalar() or 0

    # Count papers that have both policy scores and venue decisions.
    paired_result = await session.execute(
        select(func.count(func.distinct(Review.paper_id)))
        .join(SubmissionOutcome, SubmissionOutcome.paper_id == Review.paper_id)
        .where(
            Review.policy_scores_json.isnot(None),
            SubmissionOutcome.decision.isnot(None),
        )
    )
    papers_with_scores_and_outcomes = paired_result.scalar() or 0

    # Recent 1c experiments.
    exp_result = await session.execute(
        select(RSIExperiment)
        .where(RSIExperiment.tier == "1c")
        .order_by(RSIExperiment.created_at.desc())
        .limit(5)
    )
    experiments = exp_result.scalars().all()
    recent_experiments = [
        {
            "id": exp.id,
            "name": exp.name,
            "status": exp.status,
            "created_at": exp.created_at.isoformat() if exp.created_at else None,
            "result_summary": safe_json_loads(exp.result_summary_json, None),
        }
        for exp in experiments
    ]

    # Count total prompt versions for weights.
    pv_count_result = await session.execute(
        select(func.count()).where(
            PromptVersion.target_type == _WEIGHTS_TARGET_TYPE,
            PromptVersion.target_key == _WEIGHTS_TARGET_KEY,
        )
    )
    weight_versions = pv_count_result.scalar() or 0

    return {
        "active_weights": active_weights,
        "is_default_weights": active_weights_text is None,
        "weight_versions": weight_versions,
        "papers_with_policy_scores": papers_with_scores,
        "papers_with_scores_and_outcomes": papers_with_scores_and_outcomes,
        "sufficient_data": papers_with_scores_and_outcomes >= _MIN_SAMPLE_SIZE,
        "recent_experiments": recent_experiments,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_mean(values: list[float]) -> float:
    """Return the arithmetic mean, or 0.0 for an empty list."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_std(values: list[float], mean: float) -> float:
    """Return the sample standard deviation, or 0.0 for fewer than 2 values."""
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _point_biserial(
    group_a: list[float],
    group_b: list[float],
) -> float:
    """Compute a point-biserial correlation coefficient between a binary
    variable (group membership) and a continuous variable (score values).

    group_a = scores where binary variable = 1 (accepted).
    group_b = scores where binary variable = 0 (rejected).

    Returns r_pb in [-1, 1], or 0.0 when computation is not possible.
    """
    n_a = len(group_a)
    n_b = len(group_b)
    n = n_a + n_b

    if n < 2 or n_a == 0 or n_b == 0:
        return 0.0

    mean_a = _safe_mean(group_a)
    mean_b = _safe_mean(group_b)

    # Pooled standard deviation of all values.
    all_values = group_a + group_b
    overall_mean = _safe_mean(all_values)
    s = _safe_std(all_values, overall_mean)

    if s == 0:
        return 0.0

    # r_pb = (M1 - M0) / s * sqrt(n1*n0 / n^2)
    r_pb = ((mean_a - mean_b) / s) * math.sqrt((n_a * n_b) / (n * n))
    # Clamp to [-1, 1] to guard against floating-point drift.
    return max(-1.0, min(1.0, r_pb))
