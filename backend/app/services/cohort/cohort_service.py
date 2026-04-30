"""Cohort tagging and cross-cohort comparison service."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.cohort_tag import CohortTag
from app.models.rating import Rating

logger = logging.getLogger(__name__)


def _current_cohort_id(generation_model: str) -> str:
    """Generate a cohort ID from current quarter and model."""
    now = datetime.now(timezone.utc)
    quarter = (now.month - 1) // 3 + 1
    # Shorten model name for readability
    short_model = generation_model.split("/")[-1].replace("claude-", "").replace("-", "")[:10]
    return f"{now.year}-Q{quarter}-{short_model}"


async def tag_paper_cohort(
    session: AsyncSession,
    paper_id: str,
    generation_model: str | None = None,
    review_models: list[str] | None = None,
    judge_model: str | None = None,
) -> CohortTag:
    """Tag a paper with its cohort based on the current model configuration."""
    if generation_model is None:
        generation_model = settings.claude_opus_model
    cohort_id = _current_cohort_id(generation_model)

    # Check if already tagged
    result = await session.execute(
        select(CohortTag).where(CohortTag.paper_id == paper_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        logger.info("Paper %s already tagged with cohort %s", paper_id, existing.cohort_id)
        return existing

    tag = CohortTag(
        paper_id=paper_id,
        cohort_id=cohort_id,
        generation_model=generation_model,
        review_models_json=json.dumps(review_models or []),
        tournament_judge_model=judge_model,
    )
    session.add(tag)
    await session.flush()

    logger.info("Tagged paper %s with cohort %s", paper_id, cohort_id)
    return tag


async def get_cohort_comparison(
    session: AsyncSession, cohort_id: str | None = None
) -> dict:
    """Compare metrics across cohorts or for a specific cohort."""
    query = select(CohortTag)
    if cohort_id:
        query = query.where(CohortTag.cohort_id == cohort_id)

    result = await session.execute(query)
    tags = result.scalars().all()

    # Group by cohort
    cohorts: dict[str, list[str]] = {}
    for tag in tags:
        cohorts.setdefault(tag.cohort_id, []).append(tag.paper_id)

    comparison = []
    for cid, paper_ids in cohorts.items():
        # Get ratings for papers in this cohort
        ratings_result = await session.execute(
            select(Rating).where(Rating.paper_id.in_(paper_ids))
        )
        ratings = ratings_result.scalars().all()

        avg_mu = sum(r.mu for r in ratings) / len(ratings) if ratings else 0.0
        avg_conservative = sum(r.conservative_rating for r in ratings) / len(ratings) if ratings else 0.0

        # Get the generation model from any tag in this cohort
        sample_tag = next((t for t in tags if t.cohort_id == cid), None)

        comparison.append({
            "cohort_id": cid,
            "paper_count": len(paper_ids),
            "generation_model": sample_tag.generation_model if sample_tag else "unknown",
            "avg_mu": round(avg_mu, 2),
            "avg_conservative_rating": round(avg_conservative, 2),
            "rated_papers": len(ratings),
        })

    return {"cohorts": comparison}


async def get_cross_cohort_trends(session: AsyncSession) -> list[dict]:
    """Time series of cohort-level metrics."""
    result = await session.execute(
        select(CohortTag).order_by(CohortTag.created_at)
    )
    tags = result.scalars().all()

    # Group by cohort, preserving order
    seen: dict[str, dict] = {}
    for tag in tags:
        if tag.cohort_id not in seen:
            seen[tag.cohort_id] = {
                "cohort_id": tag.cohort_id,
                "generation_model": tag.generation_model,
                "first_paper_at": tag.created_at.isoformat() if tag.created_at else None,
                "paper_count": 0,
            }
        seen[tag.cohort_id]["paper_count"] += 1

    return list(seen.values())
