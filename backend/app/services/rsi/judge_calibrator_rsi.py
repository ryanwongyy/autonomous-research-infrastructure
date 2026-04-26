"""Tier 2c: Correlates tournament rankings with venue outcomes to calibrate judge prompts."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.rating import Rating
from app.models.submission_outcome import SubmissionOutcome
from app.services.rsi.experiment_manager import create_experiment
from app.services.rsi.prompt_registry import get_active_prompt, register_prompt

logger = logging.getLogger(__name__)

# Numeric scores assigned to venue decisions for correlation analysis
_DECISION_SCORES: dict[str, int] = {
    "accepted": 3,
    "r_and_r": 2,
    "rejected": 1,
    "desk_reject": 0,
}

# Minimum papers with both a rank and an outcome to run calibration
_MIN_SAMPLE_SIZE = 5


async def correlate_rankings_with_outcomes(
    session: AsyncSession,
    family_id: str,
) -> dict:
    """Compute rank-outcome correlation for a family.

    Joins Rating with SubmissionOutcome via paper_id, then computes
    Spearman rank correlation and concordance rate between tournament
    rank and venue decision quality.
    """
    # Fetch papers that have both a rating rank and a submission outcome
    query = (
        select(
            Rating.paper_id,
            Rating.rank,
            SubmissionOutcome.decision,
        )
        .join(SubmissionOutcome, SubmissionOutcome.paper_id == Rating.paper_id)
        .where(
            Rating.family_id == family_id,
            Rating.rank.isnot(None),
            SubmissionOutcome.decision.isnot(None),
        )
        .order_by(Rating.rank.asc())
    )
    result = await session.execute(query)
    rows = result.all()

    if not rows:
        return {
            "family_id": family_id,
            "sample_size": 0,
            "rank_outcome_pairs": [],
            "spearman_rho": 0.0,
            "concordance_rate": 0.0,
            "misranked_papers": [],
        }

    # Build pairs: (paper_id, rank, decision, decision_score)
    pairs: list[dict] = []
    for paper_id, rank, decision in rows:
        pairs.append({
            "paper_id": paper_id,
            "rank": rank,
            "decision": decision,
            "decision_score": _DECISION_SCORES.get(decision, 0),
        })

    sample_size = len(pairs)

    # -- Spearman rank correlation (manual, no scipy) -------------------------
    # Rank the decision_scores (higher is better) and compare with tournament rank
    # Tournament rank: lower is better (rank 1 = best)
    # Decision score: higher is better
    # For Spearman: we need ranks of both variables

    # Rank of tournament rank is itself (already ordered)
    # Assign fractional ranks to decision scores
    decision_scores = [p["decision_score"] for p in pairs]
    outcome_ranks = _fractional_ranks(decision_scores, ascending=False)
    tournament_ranks = _fractional_ranks(
        [p["rank"] for p in pairs], ascending=True
    )

    spearman_rho = _compute_spearman(tournament_ranks, outcome_ranks)

    # -- Concordance rate -----------------------------------------------------
    # For each pair (i, j) where i has better rank than j, check if i also
    # has a better or equal decision outcome
    concordant = 0
    discordant = 0
    for i in range(sample_size):
        for j in range(i + 1, sample_size):
            rank_diff = pairs[i]["rank"] - pairs[j]["rank"]
            score_diff = pairs[i]["decision_score"] - pairs[j]["decision_score"]
            if rank_diff == 0 or score_diff == 0:
                continue  # tied, skip
            if (rank_diff < 0 and score_diff > 0) or (rank_diff > 0 and score_diff < 0):
                # rank_diff < 0 means i has better rank; score_diff > 0 means i has better outcome
                concordant += 1
            else:
                discordant += 1

    total_comparable = concordant + discordant
    concordance_rate = concordant / total_comparable if total_comparable > 0 else 0.0

    # -- Identify misranked papers --------------------------------------------
    # High rank (low number) but rejected/desk_reject, or
    # Low rank (high number) but accepted
    median_rank = sample_size / 2
    misranked: list[dict] = []
    for p in pairs:
        is_high_rank = p["rank"] <= median_rank
        is_bad_outcome = p["decision"] in ("rejected", "desk_reject")
        is_low_rank = p["rank"] > median_rank
        is_good_outcome = p["decision"] == "accepted"

        if (is_high_rank and is_bad_outcome) or (is_low_rank and is_good_outcome):
            misranked.append({
                "paper_id": p["paper_id"],
                "rank": p["rank"],
                "decision": p["decision"],
            })

    rank_outcome_pairs = [
        {"paper_id": p["paper_id"], "rank": p["rank"], "decision": p["decision"]}
        for p in pairs
    ]

    return {
        "family_id": family_id,
        "sample_size": sample_size,
        "rank_outcome_pairs": rank_outcome_pairs,
        "spearman_rho": round(spearman_rho, 4),
        "concordance_rate": round(concordance_rate, 4),
        "misranked_papers": misranked,
    }


async def propose_judge_adjustment(
    session: AsyncSession,
    family_id: str,
    correlation_report: dict,
) -> dict:
    """Propose judge prompt adjustments based on correlation analysis.

    Analyses misranked papers to detect systematic bias, then registers a
    new prompt version with targeted fixes.
    """
    adjustments: list[str] = []
    misranked = correlation_report.get("misranked_papers", [])
    spearman_rho = correlation_report.get("spearman_rho", 0.0)
    concordance_rate = correlation_report.get("concordance_rate", 0.0)
    sample_size = correlation_report.get("sample_size", 0)

    if sample_size < _MIN_SAMPLE_SIZE:
        return {
            "experiment_id": None,
            "prompt_version_id": None,
            "adjustments": [],
            "expected_improvement": (
                f"Insufficient data: only {sample_size} papers have both "
                f"rankings and outcomes (need {_MIN_SAMPLE_SIZE})."
            ),
        }

    # -- Analyse misranked papers for method bias -----------------------------
    # Load methods for misranked papers
    misranked_ids = [m["paper_id"] for m in misranked]
    method_bias: dict[str, dict[str, int]] = {}  # method -> {overranked: n, underranked: n}

    if misranked_ids:
        method_result = await session.execute(
            select(Paper.id, Paper.method).where(Paper.id.in_(misranked_ids))
        )
        paper_methods = {row.id: row.method for row in method_result.all()}

        median_rank = sample_size / 2
        for m in misranked:
            method = paper_methods.get(m["paper_id"])
            if method is None:
                continue
            if method not in method_bias:
                method_bias[method] = {"overranked": 0, "underranked": 0}
            if m["rank"] <= median_rank and m["decision"] in ("rejected", "desk_reject"):
                method_bias[method]["overranked"] += 1
            elif m["rank"] > median_rank and m["decision"] == "accepted":
                method_bias[method]["underranked"] += 1

    # Generate adjustment suggestions
    for method, counts in method_bias.items():
        if counts["overranked"] > counts["underranked"] and counts["overranked"] >= 2:
            adjustments.append(
                f"Judge appears to overvalue '{method}' papers: "
                f"{counts['overranked']} ranked highly but rejected. "
                "Add emphasis on external validity and venue-specific criteria."
            )
        elif counts["underranked"] > counts["overranked"] and counts["underranked"] >= 2:
            adjustments.append(
                f"Judge appears to undervalue '{method}' papers: "
                f"{counts['underranked']} ranked low but accepted. "
                "Reduce penalty for this method; recalibrate novelty expectations."
            )

    # General correlation-based adjustments
    if spearman_rho < 0.3:
        adjustments.append(
            f"Weak rank-outcome correlation (rho={spearman_rho:.2f}). "
            "Judge criteria may be divergent from real venue standards. "
            "Consider grounding the rubric in published acceptance criteria."
        )

    if concordance_rate < 0.5:
        adjustments.append(
            f"Low concordance rate ({concordance_rate:.0%}). "
            "Pairwise comparisons are worse than chance at predicting "
            "real-world outcomes. Major prompt revision recommended."
        )

    if not adjustments:
        adjustments.append(
            "No systematic bias detected. Minor tuning may still help; "
            "consider reviewing borderline cases for calibration insights."
        )

    # -- Build new prompt text ------------------------------------------------
    current_prompt = await get_active_prompt(session, "judge", family_id)
    base_prompt = current_prompt or f"[Default judge prompt for family {family_id}]"

    # Append calibration notes as addendum
    calibration_addendum = (
        "\n\n--- CALIBRATION NOTES (auto-generated) ---\n"
        + "\n".join(f"- {a}" for a in adjustments)
        + f"\n\n[Based on {sample_size} papers; Spearman rho={spearman_rho:.2f}, "
        f"concordance={concordance_rate:.0%}]"
    )
    new_prompt_text = base_prompt + calibration_addendum

    # -- Create experiment and register prompt --------------------------------
    experiment = await create_experiment(
        session,
        tier="2c",
        name=f"judge_calibration_{family_id}",
        family_id=family_id,
        config_snapshot={
            "spearman_rho": spearman_rho,
            "concordance_rate": concordance_rate,
            "misranked_count": len(misranked),
            "adjustments": adjustments,
        },
    )

    prompt_version = await register_prompt(
        session,
        target_type="judge",
        target_key=family_id,
        prompt_text=new_prompt_text,
        experiment_id=experiment.id,
    )

    expected_improvement = (
        f"Targeting {len(misranked)} misranked papers. "
        f"Current rho={spearman_rho:.2f}; "
        f"expect improvement toward 0.5+ with method-bias corrections."
        if misranked
        else "No misranked papers found; minor tuning only."
    )

    logger.info(
        "Proposed judge adjustment for family %s: experiment=%s, prompt_v=%s, %d adjustments",
        family_id, experiment.id, prompt_version.id, len(adjustments),
    )

    return {
        "experiment_id": experiment.id,
        "prompt_version_id": prompt_version.id,
        "adjustments": adjustments,
        "expected_improvement": expected_improvement,
    }


async def get_judge_calibration_overview(session: AsyncSession) -> list[dict]:
    """Get calibration status for all families with enough data.

    Only includes families where at least ``_MIN_SAMPLE_SIZE`` papers have
    both a tournament rank and a submission outcome.
    """
    # Find families with sufficient ranked+outcome data
    count_q = (
        select(
            Rating.family_id,
            func.count().label("cnt"),
        )
        .join(SubmissionOutcome, SubmissionOutcome.paper_id == Rating.paper_id)
        .where(
            Rating.rank.isnot(None),
            SubmissionOutcome.decision.isnot(None),
            Rating.family_id.isnot(None),
        )
        .group_by(Rating.family_id)
        .having(func.count() >= _MIN_SAMPLE_SIZE)
    )
    count_result = await session.execute(count_q)
    eligible_families = count_result.all()

    overview: list[dict] = []
    for family_id, data_count in eligible_families:
        report = await correlate_rankings_with_outcomes(session, family_id)
        overview.append({
            "family_id": family_id,
            "data_points": data_count,
            "spearman_rho": report["spearman_rho"],
            "concordance_rate": report["concordance_rate"],
            "misranked_count": len(report["misranked_papers"]),
            "needs_calibration": report["spearman_rho"] < 0.5 or report["concordance_rate"] < 0.6,
        })

    return overview


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fractional_ranks(values: list[float | int], ascending: bool = True) -> list[float]:
    """Assign fractional (averaged) ranks to a list of values.

    ``ascending=True`` means smaller values get lower ranks (rank 1 = smallest).
    ``ascending=False`` means larger values get lower ranks (rank 1 = largest).
    """
    n = len(values)
    if n == 0:
        return []

    indexed = list(enumerate(values))
    indexed.sort(key=lambda x: x[1], reverse=not ascending)

    ranks = [0.0] * n
    i = 0
    while i < n:
        # Find the group of tied values
        j = i
        while j < n - 1 and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        # Average rank for the tied group (1-based)
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1

    return ranks


def _compute_spearman(ranks_x: list[float], ranks_y: list[float]) -> float:
    """Compute Spearman rank correlation coefficient from two rank vectors.

    Uses the Pearson correlation of ranks formula:
        rho = 1 - (6 * sum(d_i^2)) / (n * (n^2 - 1))
    when there are no ties, or the general Pearson-of-ranks formula otherwise.
    """
    n = len(ranks_x)
    if n < 2:
        return 0.0

    mean_x = sum(ranks_x) / n
    mean_y = sum(ranks_y) / n

    cov_xy = sum((ranks_x[i] - mean_x) * (ranks_y[i] - mean_y) for i in range(n))
    var_x = sum((ranks_x[i] - mean_x) ** 2 for i in range(n))
    var_y = sum((ranks_y[i] - mean_y) ** 2 for i in range(n))

    denominator = (var_x * var_y) ** 0.5
    if denominator == 0.0:
        return 0.0

    return cov_xy / denominator
