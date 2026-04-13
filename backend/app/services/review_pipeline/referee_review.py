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

import asyncio
import logging

from sqlalchemy import select

from app.database import async_session
from app.models.paper import Paper
from app.models.review import Review
from app.services.llm.router import get_provider_for_model
from app.config import settings

logger = logging.getLogger(__name__)


def _get_referee_models() -> list[str]:
    """Return available referee models based on configured API keys."""
    models = ["gpt-4o", "claude-sonnet-4-6"]
    if settings.google_api_key:
        models.append("gemini-2.0-flash")
    else:
        models.append("gpt-4o-mini")  # Third reviewer fallback
    return models

REFEREE_PROMPT = """You are Referee {number} reviewing a research paper for a top academic journal.

Provide a structured peer review covering:

1. SUMMARY: Brief summary of the paper's contribution
2. STRENGTHS: Key strengths (bullet points)
3. WEAKNESSES: Key weaknesses (bullet points)
4. MINOR COMMENTS: Specific suggestions for improvement
5. VERDICT: Overall assessment

Paper content:
{content}

Conclude with one of:
- "ACCEPT" - Ready for publication
- "MINOR_REVISION" - Acceptable with minor changes
- "MAJOR_REVISION" - Significant changes needed
- "REJECT" - Not suitable for publication"""


async def run_referee_review(paper_id: str) -> list[str]:
    """Run 3 parallel peer reviews."""
    async with async_session() as db:
        paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one()
        content = paper.abstract or paper.title

    async def _single_referee(model: str, number: int) -> tuple[str, str, str]:
        provider = get_provider_for_model(model)
        response = await provider.complete(
            messages=[
                {
                    "role": "user",
                    "content": REFEREE_PROMPT.format(number=number, content=content),
                }
            ],
            model=model,
            temperature=0.5,
        )
        # Parse verdict from response
        response_upper = response.upper()
        if "ACCEPT" in response_upper[-300:] and "REVISION" not in response_upper[-300:]:
            verdict = "pass"
        elif "MINOR_REVISION" in response_upper[-300:]:
            verdict = "revision_needed"
        elif "MAJOR_REVISION" in response_upper[-300:]:
            verdict = "revision_needed"
        else:
            verdict = "fail"

        return model, verdict, response

    referee_models = _get_referee_models()
    results = await asyncio.gather(
        *[_single_referee(m, i + 1) for i, m in enumerate(referee_models)],
        return_exceptions=True,
    )

    verdicts = []
    async with async_session() as db:
        for result in results:
            if isinstance(result, Exception):
                logger.error("Referee review failed: %s", result)
                continue

            model, verdict, response = result
            review = Review(
                paper_id=paper_id,
                stage="referee",
                model_used=model,
                verdict=verdict,
                content=response[:3000],
            )
            db.add(review)
            verdicts.append(verdict)

        await db.commit()

    return verdicts
