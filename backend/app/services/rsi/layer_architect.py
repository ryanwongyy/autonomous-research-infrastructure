"""Tier 3a: Audits review layer effectiveness and proposes conditional bypasses or new shadow layers."""

from __future__ import annotations

import json
import logging

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correction_record import CorrectionRecord
from app.models.failure_record import FailureRecord
from app.models.review import Review
from app.models.review_layer_config import ReviewLayerConfig
from app.models.submission_outcome import SubmissionOutcome
from app.services.rsi.experiment_manager import create_experiment
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

REVIEW_LAYERS = ["l1_structural", "l2_provenance", "l3_method", "l4_adversarial", "l5_human"]

MARGINAL_CATCH_RATE_THRESHOLD = 0.02


async def audit_layer_effectiveness(
    session: AsyncSession,
    family_id: str | None = None,
) -> list[dict]:
    """Audit all review layers for effectiveness.

    For each layer, compute:
    - total_reviews: count of reviews at this stage
    - pass_rate: fraction with verdict="pass"
    - fail_rate: fraction with verdict="fail"
    - catch_rate: failures caught by this layer (reviews with verdict=fail
      that have matching FailureRecord)
    - marginal_catch_rate: failures caught ONLY by this layer and not by any
      other (unique catches)
    - false_negative_count: papers passing this layer that later got rejected
      at venue or had corrections
    - false_positive_count: papers failing this layer that later succeeded

    Returns list of dicts, one per layer.
    """
    results: list[dict] = []

    for layer in REVIEW_LAYERS:
        # ---- basic review counts ----
        base_filter = [Review.stage == layer]
        if family_id is not None:
            base_filter.append(Review.family_id == family_id)

        counts_q = select(
            func.count().label("total"),
            func.count(case((Review.verdict == "pass", 1))).label("pass_count"),
            func.count(case((Review.verdict == "fail", 1))).label("fail_count"),
        ).where(*base_filter)

        counts_row = (await session.execute(counts_q)).one()
        total_reviews = counts_row.total
        pass_count = counts_row.pass_count
        fail_count = counts_row.fail_count

        pass_rate = pass_count / total_reviews if total_reviews else 0.0
        fail_rate = fail_count / total_reviews if total_reviews else 0.0

        # ---- catch_rate: failed reviews that have a FailureRecord at this stage ----
        catch_filter = [
            Review.stage == layer,
            Review.verdict == "fail",
            FailureRecord.detection_stage == layer,
            FailureRecord.paper_id == Review.paper_id,
        ]
        if family_id is not None:
            catch_filter.append(Review.family_id == family_id)

        catch_q = (
            select(func.count(func.distinct(FailureRecord.paper_id)))
            .select_from(Review)
            .join(
                FailureRecord,
                and_(
                    FailureRecord.paper_id == Review.paper_id,
                    FailureRecord.detection_stage == layer,
                ),
            )
            .where(Review.stage == layer, Review.verdict == "fail")
        )
        if family_id is not None:
            catch_q = catch_q.where(Review.family_id == family_id)

        caught_count = (await session.execute(catch_q)).scalar() or 0
        catch_rate = caught_count / total_reviews if total_reviews else 0.0

        # ---- marginal_catch_rate: failures detected ONLY at this layer ----
        # Get paper_ids of failures detected at this layer
        papers_caught_here_q = select(FailureRecord.paper_id).where(
            FailureRecord.detection_stage == layer
        )
        if family_id is not None:
            papers_caught_here_q = papers_caught_here_q.where(FailureRecord.family_id == family_id)
        papers_caught_here_q = papers_caught_here_q.distinct()
        papers_caught_here = {row[0] for row in (await session.execute(papers_caught_here_q)).all()}

        # For each such paper, check if it was ALSO caught at another layer
        other_layers = [lyr for lyr in REVIEW_LAYERS if lyr != layer]
        if papers_caught_here and other_layers:
            also_caught_q = (
                select(FailureRecord.paper_id)
                .where(
                    FailureRecord.paper_id.in_(papers_caught_here),
                    FailureRecord.detection_stage.in_(other_layers),
                )
                .distinct()
            )
            also_caught = {row[0] for row in (await session.execute(also_caught_q)).all()}
        else:
            also_caught = set()

        unique_catches = len(papers_caught_here - also_caught)
        marginal_catch_rate = unique_catches / total_reviews if total_reviews else 0.0

        # ---- false_negative_count: papers that PASSED this layer but later ----
        # got rejected at a venue or had corrections
        passed_paper_ids_q = select(Review.paper_id).where(
            Review.stage == layer, Review.verdict == "pass"
        )
        if family_id is not None:
            passed_paper_ids_q = passed_paper_ids_q.where(Review.family_id == family_id)
        passed_paper_ids_q = passed_paper_ids_q.distinct()

        passed_ids_sub = passed_paper_ids_q.subquery()

        # Papers rejected at venue
        venue_rejected_q = select(func.count(func.distinct(SubmissionOutcome.paper_id))).where(
            SubmissionOutcome.paper_id.in_(select(passed_ids_sub.c.paper_id)),
            SubmissionOutcome.decision.in_(["rejected", "desk_reject"]),
        )
        venue_rejected_count = (await session.execute(venue_rejected_q)).scalar() or 0

        # Papers with corrections
        corrections_q = select(func.count(func.distinct(CorrectionRecord.paper_id))).where(
            CorrectionRecord.paper_id.in_(select(passed_ids_sub.c.paper_id)),
        )
        corrections_count = (await session.execute(corrections_q)).scalar() or 0

        false_negative_count = venue_rejected_count + corrections_count

        # ---- false_positive_count: papers that FAILED this layer but later succeeded ----
        failed_paper_ids_q = select(Review.paper_id).where(
            Review.stage == layer, Review.verdict == "fail"
        )
        if family_id is not None:
            failed_paper_ids_q = failed_paper_ids_q.where(Review.family_id == family_id)
        failed_paper_ids_q = failed_paper_ids_q.distinct()

        failed_ids_sub = failed_paper_ids_q.subquery()

        venue_accepted_q = select(func.count(func.distinct(SubmissionOutcome.paper_id))).where(
            SubmissionOutcome.paper_id.in_(select(failed_ids_sub.c.paper_id)),
            SubmissionOutcome.decision.in_(["accepted", "r_and_r"]),
        )
        false_positive_count = (await session.execute(venue_accepted_q)).scalar() or 0

        results.append(
            {
                "layer": layer,
                "total_reviews": total_reviews,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "pass_rate": round(pass_rate, 4),
                "fail_rate": round(fail_rate, 4),
                "catch_rate": round(catch_rate, 4),
                "caught_count": caught_count,
                "unique_catches": unique_catches,
                "marginal_catch_rate": round(marginal_catch_rate, 4),
                "false_negative_count": false_negative_count,
                "false_positive_count": false_positive_count,
            }
        )

    return results


async def propose_layer_bypass(
    session: AsyncSession,
    layer_name: str,
    family_id: str,
    condition: dict | None = None,
) -> dict:
    """Propose bypassing a layer for a specific family.

    Only propose bypass if marginal_catch_rate < 0.02 (catches <2% of unique
    failures).

    Creates ReviewLayerConfig with status="proposed" and bypass conditions.
    Creates RSIExperiment.

    Returns: {"experiment_id": int, "layer_config_id": int, "rationale": str}
    """
    if layer_name not in REVIEW_LAYERS:
        raise ValueError(
            f"Invalid layer '{layer_name}'. Must be one of: {', '.join(REVIEW_LAYERS)}"
        )

    # Audit this specific layer for the family
    audit = await audit_layer_effectiveness(session, family_id=family_id)
    layer_stats = next((s for s in audit if s["layer"] == layer_name), None)

    if layer_stats is None:
        raise ValueError(f"No audit data available for layer '{layer_name}'")

    marginal = layer_stats["marginal_catch_rate"]
    if marginal >= MARGINAL_CATCH_RATE_THRESHOLD:
        raise ValueError(
            f"Cannot bypass '{layer_name}' for family '{family_id}': "
            f"marginal_catch_rate={marginal:.4f} >= threshold {MARGINAL_CATCH_RATE_THRESHOLD}. "
            f"Layer still catches {layer_stats['unique_catches']} unique failures."
        )

    # Build rationale
    rationale = (
        f"Layer '{layer_name}' has marginal_catch_rate={marginal:.4f} "
        f"(< {MARGINAL_CATCH_RATE_THRESHOLD}) for family '{family_id}'. "
        f"Total reviews: {layer_stats['total_reviews']}, "
        f"unique catches: {layer_stats['unique_catches']}, "
        f"false negatives: {layer_stats['false_negative_count']}."
    )

    bypass_condition = condition or {
        "reason": "low_marginal_catch_rate",
        "threshold": MARGINAL_CATCH_RATE_THRESHOLD,
    }

    # Create experiment
    experiment = await create_experiment(
        session,
        tier="3a",
        name=f"bypass_{layer_name}_for_{family_id}",
        family_id=family_id,
        config_snapshot={
            "layer_name": layer_name,
            "family_id": family_id,
            "bypass_condition": bypass_condition,
            "audit_stats": layer_stats,
        },
    )

    # Create layer config
    config = ReviewLayerConfig(
        layer_name=layer_name,
        family_id=family_id,
        status="proposed",
        bypass_condition_json=json.dumps(bypass_condition),
        effectiveness_score=marginal,
        experiment_id=experiment.id,
    )
    session.add(config)
    await session.flush()

    logger.info(
        "Proposed bypass for layer %s (family=%s, experiment=%s, config=%s)",
        layer_name,
        family_id,
        experiment.id,
        config.id,
    )

    return {
        "experiment_id": experiment.id,
        "layer_config_id": config.id,
        "rationale": rationale,
    }


async def enable_shadow_layer(
    session: AsyncSession,
    layer_name: str,
    family_id: str | None = None,
) -> dict:
    """Enable a layer in shadow mode (runs but doesn't affect pass/fail decisions).

    Creates ReviewLayerConfig with status="shadow".
    Returns config dict.
    """
    if layer_name not in REVIEW_LAYERS:
        raise ValueError(
            f"Invalid layer '{layer_name}'. Must be one of: {', '.join(REVIEW_LAYERS)}"
        )

    config = ReviewLayerConfig(
        layer_name=layer_name,
        family_id=family_id,
        status="shadow",
        shadow_results_json=json.dumps([]),  # will be populated as reviews run
    )
    session.add(config)
    await session.flush()

    logger.info(
        "Enabled shadow layer %s (family=%s, config=%s)",
        layer_name,
        family_id,
        config.id,
    )

    return {
        "id": config.id,
        "layer_name": config.layer_name,
        "family_id": config.family_id,
        "status": config.status,
    }


async def evaluate_shadow_results(
    session: AsyncSession,
    layer_config_id: int,
) -> dict:
    """Evaluate shadow layer results vs actual outcomes.

    Returns: {
        "catch_rate": float,
        "would_have_prevented": int,
        "false_alarm_rate": float,
        "recommendation": str,
    }
    """
    # Load the shadow config
    result = await session.execute(
        select(ReviewLayerConfig).where(ReviewLayerConfig.id == layer_config_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise ValueError(f"ReviewLayerConfig {layer_config_id} not found")

    if config.status != "shadow":
        raise ValueError(
            f"Config {layer_config_id} is not in shadow mode (status='{config.status}')"
        )

    layer_name = config.layer_name
    family_id = config.family_id

    # Get all reviews at this layer in shadow mode (reviews created after the config)
    review_filter = [Review.stage == layer_name]
    if family_id is not None:
        review_filter.append(Review.family_id == family_id)
    if config.updated_at is not None:
        review_filter.append(Review.created_at >= config.updated_at)

    shadow_reviews_q = select(Review).where(*review_filter)
    shadow_reviews_result = await session.execute(shadow_reviews_q)
    shadow_reviews = shadow_reviews_result.scalars().all()

    if not shadow_reviews:
        return {
            "catch_rate": 0.0,
            "would_have_prevented": 0,
            "false_alarm_rate": 0.0,
            "recommendation": "insufficient_data",
        }

    total = len(shadow_reviews)
    shadow_fails = [r for r in shadow_reviews if r.verdict == "fail"]
    shadow_fail_ids = {r.paper_id for r in shadow_fails}

    # Check how many of those shadow-fail papers ended up with real problems
    would_have_prevented = 0
    if shadow_fail_ids:
        # Papers that were later rejected or had corrections
        problem_q = select(func.count(func.distinct(SubmissionOutcome.paper_id))).where(
            SubmissionOutcome.paper_id.in_(shadow_fail_ids),
            SubmissionOutcome.decision.in_(["rejected", "desk_reject"]),
        )
        venue_problems = (await session.execute(problem_q)).scalar() or 0

        correction_q = select(func.count(func.distinct(CorrectionRecord.paper_id))).where(
            CorrectionRecord.paper_id.in_(shadow_fail_ids),
        )
        correction_problems = (await session.execute(correction_q)).scalar() or 0

        would_have_prevented = venue_problems + correction_problems

    # Catch rate: shadow fails that were real problems / total shadow reviews
    catch_rate = would_have_prevented / total if total else 0.0

    # False alarm rate: shadow fails that did NOT have problems / total shadow fails
    false_alarms = len(shadow_fail_ids) - would_have_prevented
    false_alarm_rate = false_alarms / len(shadow_fail_ids) if shadow_fail_ids else 0.0

    # Recommendation
    if catch_rate >= 0.05 and false_alarm_rate < 0.50:
        recommendation = "activate"
    elif catch_rate >= 0.02:
        recommendation = "extend_shadow"
    elif total < 20:
        recommendation = "insufficient_data"
    else:
        recommendation = "discard"

    # Persist summary back to the config
    summary = {
        "catch_rate": round(catch_rate, 4),
        "would_have_prevented": would_have_prevented,
        "false_alarm_rate": round(false_alarm_rate, 4),
        "recommendation": recommendation,
        "total_shadow_reviews": total,
        "shadow_fail_count": len(shadow_fail_ids),
    }
    config.shadow_results_json = json.dumps(summary)
    config.effectiveness_score = round(catch_rate, 4)

    logger.info(
        "Evaluated shadow config %s: catch_rate=%.4f, recommendation=%s",
        layer_config_id,
        catch_rate,
        recommendation,
    )

    return {
        "catch_rate": round(catch_rate, 4),
        "would_have_prevented": would_have_prevented,
        "false_alarm_rate": round(false_alarm_rate, 4),
        "recommendation": recommendation,
    }


async def get_layer_config(
    session: AsyncSession,
    family_id: str | None = None,
) -> list[dict]:
    """Get current layer configuration for a family (or system-wide defaults)."""
    query = select(ReviewLayerConfig)

    if family_id is not None:
        query = query.where(ReviewLayerConfig.family_id == family_id)
    else:
        # System-wide: configs with no family_id
        query = query.where(ReviewLayerConfig.family_id.is_(None))

    query = query.order_by(ReviewLayerConfig.layer_name)
    result = await session.execute(query)
    configs = result.scalars().all()

    # Build a complete picture: every layer, with config if it exists
    config_by_layer = {c.layer_name: c for c in configs}
    output: list[dict] = []

    for layer in REVIEW_LAYERS:
        cfg = config_by_layer.get(layer)
        if cfg is not None:
            output.append(
                {
                    "id": cfg.id,
                    "layer_name": cfg.layer_name,
                    "family_id": cfg.family_id,
                    "status": cfg.status,
                    "bypass_condition": safe_json_loads(cfg.bypass_condition_json, None),
                    "shadow_results": safe_json_loads(cfg.shadow_results_json, None),
                    "effectiveness_score": cfg.effectiveness_score,
                    "experiment_id": cfg.experiment_id,
                    "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
                }
            )
        else:
            # Default: layer is active with no overrides
            output.append(
                {
                    "id": None,
                    "layer_name": layer,
                    "family_id": family_id,
                    "status": "active",
                    "bypass_condition": None,
                    "shadow_results": None,
                    "effectiveness_score": None,
                    "experiment_id": None,
                    "updated_at": None,
                }
            )

    return output
