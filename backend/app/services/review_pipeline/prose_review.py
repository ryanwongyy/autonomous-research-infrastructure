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

PROSE_PROMPT = """You are a writing quality reviewer for an academic research paper.

Evaluate:
1. Clarity and precision of language
2. Logical flow between sections
3. Adherence to academic writing conventions
4. Appropriate use of citations and references
5. Absence of unsupported claims

Paper content:
{content}

{iteration_context}

Provide specific, actionable feedback. Conclude with "PASS" if writing is acceptable or "REVISION_NEEDED" with specific changes."""


async def run_prose_review(paper_id: str) -> bool:
    """Iterative prose/writing quality review (max 3 iterations)."""
    async with async_session() as db:
        paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one()
        content = paper.abstract or paper.title

    provider, model = await get_review_provider("prose")

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
                    "content": PROSE_PROMPT.format(
                        content=content, iteration_context=iteration_context
                    ),
                }
            ],
            model=model,
            temperature=0.3,
        )

        verdict = "pass" if "PASS" in response.upper()[-200:] else "revision_needed"

        async with async_session() as db:
            review = Review(
                paper_id=paper_id,
                stage="prose",
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
