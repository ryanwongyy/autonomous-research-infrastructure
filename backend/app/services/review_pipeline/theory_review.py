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

THEORY_PROMPT = """You are a theoretical economics reviewer. Review this paper for formal model correctness.

Check:
1. Mathematical consistency of any formal models
2. Validity of proofs and derivations
3. Calibration methodology (if applicable)
4. Assumptions are clearly stated and reasonable

Paper content:
{content}

If the paper does not contain formal theoretical models, respond with "NOT_APPLICABLE".
Otherwise, provide a detailed review and conclude with "PASS" or "REVISION_NEEDED"."""


async def run_theory_review(paper_id: str) -> bool:
    """Conditional theory review - only runs if paper has formal models."""
    async with async_session() as db:
        paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one()
        content = paper.abstract or paper.title

    provider, model = await get_review_provider("theory")

    response = await provider.complete(
        messages=[{"role": "user", "content": THEORY_PROMPT.format(content=content)}],
        model=model,
        temperature=0.3,
    )

    if "NOT_APPLICABLE" in response.upper():
        verdict = "pass"
    elif "PASS" in response.upper()[-200:]:
        verdict = "pass"
    else:
        verdict = "revision_needed"

    async with async_session() as db:
        review = Review(
            paper_id=paper_id,
            stage="theory",
            model_used=model,
            verdict=verdict,
            content=response[:2000],
        )
        db.add(review)
        await db.commit()

    return verdict == "pass"
