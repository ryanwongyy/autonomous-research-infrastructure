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

from app.config import settings
from app.database import async_session
from app.models.paper import Paper
from app.models.review import Review
from app.services.llm.router import get_provider_for_model

logger = logging.getLogger(__name__)


def _get_advisor_models() -> list[str]:
    """Return available advisor models based on configured API keys."""
    models = ["gpt-4o", "claude-sonnet-4-6", "gpt-4o-mini"]
    if settings.google_api_key:
        models.insert(2, "gemini-2.0-flash")
    return models


PASS_THRESHOLD = 3  # 3 of 4 must pass (or 2 of 3 when only 3 available)

ADVISOR_PROMPT = """You are a senior research advisor reviewing a paper for fatal errors.

Check for:
1. Fabricated or simulated data (must use real data)
2. Incoherent methodology or identification strategy
3. Missing core analysis or results
4. Fundamental logical errors
5. Placeholder or incomplete sections

Paper content:
{content}

Respond with either:
- "PASS" if the paper has no fatal errors (followed by brief explanation)
- "FAIL" if the paper has fatal errors (followed by specific issues found)"""


async def run_advisor_review(paper_id: str) -> bool:
    """Run multi-model advisor screening. Returns True if majority pass."""
    advisor_models = _get_advisor_models()
    threshold = min(PASS_THRESHOLD, len(advisor_models) - 1)  # Adjust for available models

    async with async_session() as db:
        paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one()
        content = paper.abstract or paper.title

    async def _single_review(model: str) -> tuple[str, str, str]:
        provider = get_provider_for_model(model)
        prompt = ADVISOR_PROMPT.format(content=content)
        response = await provider.complete(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0.3,
        )
        verdict = "pass" if "PASS" in response.upper()[:100] else "fail"
        return model, verdict, response

    results = await asyncio.gather(
        *[_single_review(m) for m in advisor_models],
        return_exceptions=True,
    )

    pass_count = 0
    async with async_session() as db:
        for result in results:
            if isinstance(result, Exception):
                logger.error("Advisor review failed for model: %s", result)
                continue

            model, verdict, response = result
            review = Review(
                paper_id=paper_id,
                stage="advisor",
                model_used=model,
                verdict=verdict,
                content=response[:2000],
            )
            db.add(review)
            if verdict == "pass":
                pass_count += 1

        await db.commit()

    logger.info("[%s] Advisor review: %d/%d passed (threshold: %d)", paper_id, pass_count, len(advisor_models), threshold)
    return pass_count >= threshold
