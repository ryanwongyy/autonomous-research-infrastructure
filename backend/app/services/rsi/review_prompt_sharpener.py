"""Tier 1b: Identifies false negatives/positives in review layers and proposes
prompt adjustments to sharpen layer accuracy."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.submission_outcome import SubmissionOutcome
from app.models.correction_record import CorrectionRecord
from app.models.failure_record import FailureRecord
from app.services.rsi.experiment_manager import create_experiment
from app.services.rsi.prompt_registry import register_prompt, get_active_prompt

logger = logging.getLogger(__name__)

# The five standard review layers.
REVIEW_LAYERS = (
    "l1_structural",
    "l2_provenance",
    "l3_method",
    "l4_adversarial",
    "l5_human",
)

# Pre-authored sharpening directives keyed by the failure type that the
# review layer missed (false negatives).
_LAYER_SHARPENING_PATCHES: dict[str, str] = {
    "hallucination": (
        "\n\nSHARPEN: Pay special attention to unsupported factual claims. "
        "Every statistic, finding, or quantitative assertion must trace back "
        "to a cited source card. Flag any claim lacking explicit provenance."
    ),
    "causal_overreach": (
        "\n\nSHARPEN: Scrutinize causal language. Unless the study design is "
        "explicitly causal (RCT, natural experiment with valid instrument), "
        "flag all deterministic causal phrases as potential overreach."
    ),
    "data_error": (
        "\n\nSHARPEN: Cross-check all data references against the source "
        "manifest. Verify sample sizes, date ranges, and variable definitions "
        "match the ingested data cards."
    ),
    "source_drift": (
        "\n\nSHARPEN: Verify that no claim exceeds the permission profile of "
        "its source card. Flag any extrapolation, generalization, or scope "
        "expansion not authorized by the source."
    ),
    "logic_error": (
        "\n\nSHARPEN: Trace each logical chain step-by-step. Verify that "
        "conclusions follow from the premises, that conditional statements are "
        "properly bounded, and that no logical fallacies are present."
    ),
    "design_violation": (
        "\n\nSHARPEN: Confirm the output conforms to the locked design "
        "specification. Check that all research questions are addressed and "
        "no unauthorized deviations exist."
    ),
    "formatting": (
        "\n\nSHARPEN: Verify venue formatting requirements including section "
        "structure, citation style, word/page limits, and figure/table rules."
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def find_false_negatives(
    session: AsyncSession,
    layer: str,
    lookback_days: int = 180,
) -> list[dict]:
    """Papers that passed a review layer but later had negative outcomes.

    A false negative is a paper where the review layer gave a 'pass' verdict
    but the paper was subsequently rejected at a venue or received a
    post-publication correction.
    """
    _validate_layer(layer)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # -- Subquery: papers that PASSED this layer (latest verdict per paper) --
    latest_review = (
        select(
            Review.paper_id,
            func.max(Review.iteration).label("max_iter"),
        )
        .where(Review.stage == layer, Review.created_at >= cutoff)
        .group_by(Review.paper_id)
        .subquery()
    )

    passed_reviews_q = (
        select(Review.paper_id)
        .join(
            latest_review,
            and_(
                Review.paper_id == latest_review.c.paper_id,
                Review.iteration == latest_review.c.max_iter,
            ),
        )
        .where(Review.stage == layer, Review.verdict == "pass")
    )

    passed_result = await session.execute(passed_reviews_q)
    passed_paper_ids = {row.paper_id for row in passed_result.all()}

    if not passed_paper_ids:
        return []

    false_negatives: list[dict] = []

    # -- Check submission outcomes (rejected / desk_reject) --
    outcome_result = await session.execute(
        select(SubmissionOutcome).where(
            SubmissionOutcome.paper_id.in_(passed_paper_ids),
            SubmissionOutcome.decision.in_(["rejected", "desk_reject"]),
        )
    )
    for out in outcome_result.scalars().all():
        false_negatives.append({
            "paper_id": out.paper_id,
            "review_verdict": "pass",
            "outcome": "venue_rejection",
            "outcome_detail": f"{out.decision} at {out.venue_name}",
        })

    # -- Check correction records --
    correction_result = await session.execute(
        select(CorrectionRecord).where(
            CorrectionRecord.paper_id.in_(passed_paper_ids),
        )
    )
    for cr in correction_result.scalars().all():
        false_negatives.append({
            "paper_id": cr.paper_id,
            "review_verdict": "pass",
            "outcome": "correction",
            "outcome_detail": f"{cr.correction_type}: {cr.description[:200]}",
        })

    return false_negatives


async def find_false_positives(
    session: AsyncSession,
    layer: str,
    lookback_days: int = 180,
) -> list[dict]:
    """Papers failed/flagged by a review layer that later succeeded.

    A false positive is a paper where the review layer gave a 'fail' or
    'revision_needed' verdict but the paper eventually passed all review
    layers and was accepted at a venue.
    """
    _validate_layer(layer)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # -- Subquery: papers that FAILED this layer at some point --
    latest_fail_review = (
        select(
            Review.paper_id,
            func.max(Review.iteration).label("max_iter"),
        )
        .where(
            Review.stage == layer,
            Review.verdict.in_(["fail", "revision_needed"]),
            Review.created_at >= cutoff,
        )
        .group_by(Review.paper_id)
        .subquery()
    )

    # Get the actual paper_ids that had a fail/revision_needed at this layer.
    failed_papers_result = await session.execute(
        select(latest_fail_review.c.paper_id)
    )
    failed_paper_ids = {row.paper_id for row in failed_papers_result.all()}

    if not failed_paper_ids:
        return []

    # Among those, find papers that were eventually accepted at a venue.
    accepted_result = await session.execute(
        select(SubmissionOutcome).where(
            SubmissionOutcome.paper_id.in_(failed_paper_ids),
            SubmissionOutcome.decision.in_(["accepted", "r_and_r"]),
        )
    )

    false_positives: list[dict] = []
    for out in accepted_result.scalars().all():
        false_positives.append({
            "paper_id": out.paper_id,
            "review_verdict": "fail/revision_needed",
            "outcome": "venue_accepted",
            "outcome_detail": f"{out.decision} at {out.venue_name}",
        })

    return false_positives


async def analyze_layer_accuracy(
    session: AsyncSession,
    layer: str,
    lookback_days: int = 180,
) -> dict:
    """Compute accuracy metrics for a review layer.

    Precision = TP / (TP + FP) -- how often a "fail" verdict is justified.
    Recall    = TP / (TP + FN) -- how often real problems are caught.
    F1        = harmonic mean.

    Here, a "true positive" is a fail/revision_needed verdict on a paper that
    was subsequently rejected or corrected.  A "true negative" is a pass
    verdict on a paper that was later accepted.
    """
    _validate_layer(layer)

    fn_list = await find_false_negatives(session, layer, lookback_days)
    fp_list = await find_false_positives(session, layer, lookback_days)

    fn_count = len(fn_list)
    fp_count = len(fp_list)

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # Total reviews at this layer in the window.
    total_result = await session.execute(
        select(func.count()).where(
            Review.stage == layer,
            Review.created_at >= cutoff,
        )
    )
    total_reviews = total_result.scalar() or 0

    # Count fail/revision_needed verdicts.
    flagged_result = await session.execute(
        select(func.count()).where(
            Review.stage == layer,
            Review.verdict.in_(["fail", "revision_needed"]),
            Review.created_at >= cutoff,
        )
    )
    flagged_count = flagged_result.scalar() or 0

    # Count pass verdicts.
    passed_result = await session.execute(
        select(func.count()).where(
            Review.stage == layer,
            Review.verdict == "pass",
            Review.created_at >= cutoff,
        )
    )
    passed_count = passed_result.scalar() or 0

    # TP = flagged - FP (flagged correctly).
    tp = max(flagged_count - fp_count, 0)
    # TN = passed - FN (passed correctly).
    tn = max(passed_count - fn_count, 0)

    precision = tp / (tp + fp_count) if (tp + fp_count) > 0 else 0.0
    recall = tp / (tp + fn_count) if (tp + fn_count) > 0 else 0.0
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    # Determine which failure types this layer missed most often (from FN papers).
    fn_paper_ids = [item["paper_id"] for item in fn_list]
    missed_failure_types: list[str] = []
    if fn_paper_ids:
        missed_result = await session.execute(
            select(
                FailureRecord.failure_type,
                func.count().label("cnt"),
            )
            .where(FailureRecord.paper_id.in_(fn_paper_ids))
            .group_by(FailureRecord.failure_type)
            .order_by(func.count().desc())
            .limit(5)
        )
        missed_failure_types = [row.failure_type for row in missed_result.all()]

    return {
        "layer": layer,
        "lookback_days": lookback_days,
        "total_reviews": total_reviews,
        "flagged_count": flagged_count,
        "passed_count": passed_count,
        "false_negatives": fn_count,
        "false_positives": fp_count,
        "true_positives": tp,
        "true_negatives": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "most_missed_failure_types": missed_failure_types,
    }


async def propose_review_prompt_patch(
    session: AsyncSession,
    layer: str,
    accuracy_analysis: dict,
) -> dict:
    """Propose adjustments to a review layer's prompt based on accuracy analysis.

    If false negatives are high for specific failure types, appends targeted
    sharpening directives.  If false positives are high, adds a calibration
    note encouraging the layer to reduce over-flagging.
    """
    _validate_layer(layer)

    current_prompt = await get_active_prompt(session, "review_prompt", layer)
    if current_prompt is None:
        current_prompt = (
            f"You are the {layer} review layer in the APE pipeline. "
            "Evaluate the paper against your assigned criteria."
        )

    missed_types = accuracy_analysis.get("most_missed_failure_types", [])
    fn_count = accuracy_analysis.get("false_negatives", 0)
    fp_count = accuracy_analysis.get("false_positives", 0)

    patches: list[str] = []
    targeted: list[str] = []

    # Address false negatives with sharpening patches.
    for ftype in missed_types[:3]:
        patch_text = _LAYER_SHARPENING_PATCHES.get(ftype)
        if patch_text:
            patches.append(patch_text)
            targeted.append(ftype)

    # Address false positives with a calibration note.
    if fp_count > 0 and fn_count > 0:
        fp_ratio = fp_count / (fp_count + fn_count)
    elif fp_count > 0:
        fp_ratio = 1.0
    else:
        fp_ratio = 0.0

    if fp_ratio > 0.4:
        patches.append(
            "\n\nCALIBRATION: Recent data shows this layer is over-flagging. "
            "Before issuing a fail verdict, verify that the issue is concrete "
            "and reproducible, not merely a stylistic preference or minor "
            "ambiguity. Reserve 'fail' for clear violations; use "
            "'revision_needed' for borderline cases."
        )
        targeted.append("_over_flagging_calibration")

    if not patches:
        return {
            "experiment_id": None,
            "prompt_version_id": None,
            "patch_summary": (
                f"Layer {layer} shows no actionable accuracy issues; "
                "no patch proposed."
            ),
            "targeted_failures": [],
        }

    patched_text = current_prompt + "".join(patches)

    exp_name = (
        f"review_prompt_sharpen_{layer}_fn{fn_count}_fp{fp_count}"
    )
    experiment = await create_experiment(
        session,
        tier="1b",
        name=exp_name,
        config_snapshot={
            "layer": layer,
            "targeted_failures": targeted,
            "accuracy_summary": {
                "precision": accuracy_analysis.get("precision"),
                "recall": accuracy_analysis.get("recall"),
                "f1": accuracy_analysis.get("f1"),
                "false_negatives": fn_count,
                "false_positives": fp_count,
            },
        },
    )

    prompt_version = await register_prompt(
        session,
        target_type="review_prompt",
        target_key=layer,
        prompt_text=patched_text,
        experiment_id=experiment.id,
    )

    patch_summary = (
        f"Proposed sharpening patch for layer '{layer}': targeting "
        f"{', '.join(targeted)} (FN={fn_count}, FP={fp_count}, "
        f"F1={accuracy_analysis.get('f1', 'N/A')})."
    )
    logger.info("Tier 1b patch proposed: %s", patch_summary)

    return {
        "experiment_id": experiment.id,
        "prompt_version_id": prompt_version.id,
        "patch_summary": patch_summary,
        "targeted_failures": targeted,
    }


async def get_all_layer_accuracy(session: AsyncSession) -> list[dict]:
    """Get accuracy metrics for all 5 review layers."""
    results: list[dict] = []
    for layer in REVIEW_LAYERS:
        accuracy = await analyze_layer_accuracy(session, layer)
        results.append(accuracy)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_layer(layer: str) -> None:
    """Raise ValueError if layer is not a recognized review layer name."""
    if layer not in REVIEW_LAYERS:
        raise ValueError(
            f"Unknown review layer '{layer}'. Must be one of: "
            f"{', '.join(REVIEW_LAYERS)}"
        )
