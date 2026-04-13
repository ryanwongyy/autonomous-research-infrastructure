"""Reliability engine: computes and tracks quality metrics with thresholds.

Five metrics per paper:
1. replication_rate: fraction of reviews that passed on first iteration
2. manifest_fidelity: lock hash integrity (1.0 = intact, 0.0 = broken)
3. expert_score: average external expert score (null until Phase 3)
4. benchmark_percentile: paper's rank / total papers in family
5. correction_rate: post-publication corrections (0 until Phase 3)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correction_record import CorrectionRecord
from app.models.expert_review import ExpertReview
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating
from app.models.reliability_metric import ReliabilityMetric
from app.models.review import Review
from app.services.storage.lock_manager import verify_lock

logger = logging.getLogger(__name__)

# Default thresholds from domain config
DEFAULT_THRESHOLDS = {
    "replication_rate": 0.95,
    "manifest_fidelity": 1.0,
    "expert_score": 3.0,
    "benchmark_percentile": 0.50,
    "correction_rate": 0.05,  # Max 5% correction rate
}


async def compute_paper_reliability(
    session: AsyncSession, paper_id: str
) -> dict:
    """Compute all five reliability metrics for a single paper.

    Returns dict with metric_type -> {value, threshold, passes, details}.
    """
    metrics: dict[str, dict] = {}

    # 1. Replication rate: fraction of L1-L4 reviews that passed on first iteration
    review_result = await session.execute(
        select(Review).where(
            Review.paper_id == paper_id,
            Review.stage.in_(["l1_structural", "l2_provenance", "l3_method", "l4_adversarial"]),
        )
    )
    reviews = review_result.scalars().all()

    if reviews:
        first_iter_reviews = [r for r in reviews if r.iteration == 1]
        first_pass = sum(1 for r in first_iter_reviews if r.verdict == "pass")
        replication_rate = first_pass / len(first_iter_reviews) if first_iter_reviews else 0.0
    else:
        replication_rate = 0.0

    threshold = DEFAULT_THRESHOLDS["replication_rate"]
    metrics["replication_rate"] = {
        "value": round(replication_rate, 4),
        "threshold": threshold,
        "passes": replication_rate >= threshold,
        "details": f"{len(reviews)} total reviews, first-iteration pass rate",
    }

    # 2. Manifest fidelity: lock hash integrity
    lock_result = await verify_lock(session, paper_id)
    fidelity = 1.0 if lock_result.get("valid", False) else 0.0

    threshold = DEFAULT_THRESHOLDS["manifest_fidelity"]
    metrics["manifest_fidelity"] = {
        "value": fidelity,
        "threshold": threshold,
        "passes": fidelity >= threshold,
        "details": f"Lock hash {'intact' if fidelity == 1.0 else 'broken or missing'}",
    }

    # 3. Expert score: average ExpertReview.overall_score
    expert_result = await session.execute(
        select(func.avg(ExpertReview.overall_score)).where(
            ExpertReview.paper_id == paper_id
        )
    )
    avg_expert = expert_result.scalar()
    expert_val = float(avg_expert) if avg_expert is not None else 0.0
    has_expert_reviews = avg_expert is not None

    threshold = DEFAULT_THRESHOLDS["expert_score"]
    metrics["expert_score"] = {
        "value": round(expert_val, 2),
        "threshold": threshold,
        "passes": expert_val >= threshold if has_expert_reviews else True,
        "details": f"Average expert score: {expert_val:.1f}" if has_expert_reviews else "No external expert reviews yet",
    }

    # 4. Benchmark percentile: rank / total papers in family
    rating_result = await session.execute(
        select(Rating).where(Rating.paper_id == paper_id)
    )
    rating = rating_result.scalar_one_or_none()

    if rating and rating.rank and rating.family_id:
        total_in_family = (
            await session.execute(
                select(func.count()).select_from(Rating).where(Rating.family_id == rating.family_id)
            )
        ).scalar() or 1
        percentile = 1.0 - (rating.rank / total_in_family)
    else:
        percentile = 0.0

    threshold = DEFAULT_THRESHOLDS["benchmark_percentile"]
    metrics["benchmark_percentile"] = {
        "value": round(percentile, 4),
        "threshold": threshold,
        "passes": percentile >= threshold,
        "details": f"Rank #{rating.rank if rating else 'N/A'} in family",
    }

    # 5. Correction rate: post-publication corrections
    correction_count_result = await session.execute(
        select(func.count()).select_from(CorrectionRecord).where(
            CorrectionRecord.paper_id == paper_id
        )
    )
    correction_count = correction_count_result.scalar() or 0
    # Rate is corrections per paper (0 or more); threshold is max acceptable rate
    correction_val = float(correction_count)

    threshold = DEFAULT_THRESHOLDS["correction_rate"]
    metrics["correction_rate"] = {
        "value": correction_val,
        "threshold": threshold,
        "passes": correction_val <= threshold,
        "details": f"{correction_count} correction(s) recorded",
    }

    # Persist metrics
    now = datetime.now(timezone.utc)
    paper_result = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = paper_result.scalar_one_or_none()
    family_id = paper.family_id if paper else None

    for metric_type, data in metrics.items():
        metric = ReliabilityMetric(
            paper_id=paper_id,
            family_id=family_id,
            metric_type=metric_type,
            value=data["value"],
            threshold=data["threshold"],
            passes_threshold=data["passes"],
            computed_at=now,
            details_json=json.dumps({"details": data["details"]}),
        )
        session.add(metric)

    await session.flush()

    return metrics


async def compute_family_reliability(
    session: AsyncSession, family_id: str
) -> dict:
    """Aggregate reliability metrics across all papers in a family.

    Returns dict with metric_type -> {avg_value, min_value, max_value, papers_passing, total_papers}.
    """
    # Get latest metrics for each paper in family, grouped by type
    papers_result = await session.execute(
        select(Paper.id).where(Paper.family_id == family_id)
    )
    paper_ids = [row[0] for row in papers_result.all()]

    if not paper_ids:
        return {}

    aggregates: dict[str, dict] = {}

    for metric_type in DEFAULT_THRESHOLDS:
        # Get most recent metric of this type for each paper
        values: list[float] = []
        passing = 0

        for pid in paper_ids:
            result = await session.execute(
                select(ReliabilityMetric)
                .where(
                    ReliabilityMetric.paper_id == pid,
                    ReliabilityMetric.metric_type == metric_type,
                )
                .order_by(ReliabilityMetric.computed_at.desc())
                .limit(1)
            )
            metric = result.scalar_one_or_none()
            if metric:
                values.append(metric.value)
                if metric.passes_threshold:
                    passing += 1

        if values:
            aggregates[metric_type] = {
                "avg_value": round(sum(values) / len(values), 4),
                "min_value": round(min(values), 4),
                "max_value": round(max(values), 4),
                "papers_passing": passing,
                "total_papers": len(values),
                "threshold": DEFAULT_THRESHOLDS[metric_type],
            }

    return aggregates


async def get_reliability_overview(session: AsyncSession) -> dict:
    """System-wide reliability overview across all families."""
    families_result = await session.execute(
        select(PaperFamily).where(PaperFamily.active.is_(True))
    )
    families = families_result.scalars().all()

    overview = {
        "families": [],
        "thresholds": DEFAULT_THRESHOLDS,
    }

    for family in families:
        family_metrics = await compute_family_reliability(session, family.id)
        if family_metrics:
            overview["families"].append({
                "family_id": family.id,
                "short_name": family.short_name,
                "metrics": family_metrics,
            })

    return overview
