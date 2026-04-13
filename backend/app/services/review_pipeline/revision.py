# DEPRECATED: This module is part of the old 6-stage review pipeline.
# It has been replaced by the 5-layer architecture:
#   L1: l1_structural.py
#   L2: l2_provenance.py
#   L3: l3_method.py
#   L4: l4_adversarial.py
#   L5: l5_human_escalation.py
# See orchestrator.py for the new pipeline entry point.
# This file is retained for backward compatibility and will be removed
# in a future release.

import logging

from sqlalchemy import select

from app.database import async_session
from app.models.paper import Paper
from app.models.review import Review
from app.services.llm.router import get_review_provider

logger = logging.getLogger(__name__)

REVISION_PROMPT = """You are revising a research paper based on reviewer feedback.

Original paper content:
{content}

Reviewer feedback to address:
{feedback}

Produce a revised version that addresses all reviewer comments. Focus on:
1. Strengthening the identification strategy if questioned
2. Adding robustness checks if requested
3. Improving clarity and exposition
4. Addressing all specific concerns raised

Provide the revised paper content."""


async def run_revision(paper_id: str) -> bool:
    """Aggregate all review feedback and produce a revised paper."""
    async with async_session() as db:
        paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one()
        content = paper.abstract or paper.title

        # Gather all reviews for this paper
        reviews = (
            await db.execute(
                select(Review)
                .where(Review.paper_id == paper_id)
                .order_by(Review.stage, Review.iteration)
            )
        ).scalars().all()

    # Build feedback summary
    feedback_parts = []
    for review in reviews:
        if review.verdict in ("revision_needed", "fail"):
            feedback_parts.append(f"[{review.stage.upper()} - {review.model_used}]:\n{review.content[:500]}\n")

    if not feedback_parts:
        logger.info("[%s] No revision feedback to address", paper_id)
        async with async_session() as db:
            review = Review(
                paper_id=paper_id,
                stage="revision",
                model_used="none",
                verdict="pass",
                content="No revisions needed - all reviews passed.",
            )
            db.add(review)
            await db.commit()
        return True

    feedback = "\n---\n".join(feedback_parts)

    provider, model = await get_review_provider("revision")

    response = await provider.complete(
        messages=[
            {"role": "user", "content": REVISION_PROMPT.format(content=content, feedback=feedback)},
        ],
        model=model,
        temperature=0.5,
        max_tokens=8192,
    )

    async with async_session() as db:
        review = Review(
            paper_id=paper_id,
            stage="revision",
            model_used=model,
            verdict="pass",
            content=response[:5000],
        )
        db.add(review)
        await db.commit()

    return True
