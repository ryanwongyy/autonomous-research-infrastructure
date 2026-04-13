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

MAX_ITERATIONS = 3

EXHIBIT_PROMPT = """You are reviewing the tables and figures of a research paper.

Evaluate:
1. Are tables clearly labeled with descriptive titles?
2. Do figures have proper axes labels and legends?
3. Are standard errors or confidence intervals reported?
4. Is the formatting consistent and professional?
5. Do exhibits support the paper's claims?

Paper content:
{content}

{iteration_context}

Provide specific, actionable feedback. Conclude with "PASS" if exhibits are acceptable or "REVISION_NEEDED" with specific changes."""


async def run_exhibit_review(paper_id: str) -> bool:
    """Iterative exhibit review (max 3 iterations)."""
    async with async_session() as db:
        paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one()
        content = paper.abstract or paper.title

    provider, model = await get_review_provider("exhibit")

    for iteration in range(1, MAX_ITERATIONS + 1):
        iteration_context = (
            f"This is iteration {iteration} of the review."
            if iteration > 1
            else "This is the initial review."
        )

        response = await provider.complete(
            messages=[
                {
                    "role": "user",
                    "content": EXHIBIT_PROMPT.format(content=content, iteration_context=iteration_context),
                }
            ],
            model=model,
            temperature=0.3,
        )

        verdict = "pass" if "PASS" in response.upper()[-200:] else "revision_needed"

        async with async_session() as db:
            review = Review(
                paper_id=paper_id,
                stage="exhibit",
                model_used=model,
                verdict=verdict,
                content=response[:2000],
                iteration=iteration,
            )
            db.add(review)
            await db.commit()

        if verdict == "pass":
            return True

    return False
