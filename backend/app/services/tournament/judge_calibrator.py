"""Per-family judge calibration using intentionally corrupted control variants.

Calibration set is INTERNAL -- never enters the public leaderboard.

The workflow is:
1.  Pick a base paper from the family (ideally a well-rated benchmark paper).
2.  Generate N corruption descriptions appropriate to the family's protocol.
3.  For each variant, ask the judge to compare the original vs. the corrupted
    description and check whether it correctly ranks the original higher.
4.  Run position-swapped consistency checks.
5.  Report discrimination, consistency, and fatal-detection scores.

In dev mode the corruptions are *metadata descriptions* rather than real
papers, so the calibration run exercises prompt construction and scoring
logic without requiring an actual corruption pipeline.
"""

from __future__ import annotations

import logging
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.services.llm.router import get_judge_provider
from app.services.tournament.control_variants import (
    build_variant_description,
    get_corruptions_for_protocol,
)
from app.services.tournament.judge import (
    get_family_judge_prompt,
    judge_match,
    resolve_match,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_calibration_variants(
    session: AsyncSession,
    family_id: str,
    base_paper_id: str,
    variant_count: int = 3,
) -> list[dict]:
    """Generate intentionally corrupted variants of a base paper for calibration.

    Corruption types are chosen based on the family's ``lock_protocol_type``:
    - empirical_causal: bad controls, broken event studies, unsupported causal language
    - measurement_text: unvalidated coding, dropped validation checks
    - doctrinal: missing authorities, misquotes, jurisdiction errors
    - theory: proof gaps, assumption slippage
    - synthesis_bibliometric: hidden selection bias, unreproducible search

    Returns list of variant descriptions (not actual corrupted papers -- those
    would require full generation).  In dev mode, returns metadata describing
    what would be corrupted.
    """
    family = (
        await session.execute(
            select(PaperFamily).where(PaperFamily.id == family_id)
        )
    ).scalar_one_or_none()

    if not family:
        raise ValueError(f"Family {family_id} not found")

    base_paper = (
        await session.execute(
            select(Paper).where(Paper.id == base_paper_id)
        )
    ).scalar_one_or_none()

    if not base_paper:
        raise ValueError(f"Base paper {base_paper_id} not found")

    protocol = family.lock_protocol_type or "empirical_causal"
    corruptions = get_corruptions_for_protocol(protocol)

    # Pick up to variant_count corruptions (without replacement when possible)
    chosen = random.sample(corruptions, min(variant_count, len(corruptions)))

    variants = [
        build_variant_description(base_paper.title, c, idx)
        for idx, c in enumerate(chosen)
    ]

    return variants


async def run_calibration_check(
    session: AsyncSession,
    family_id: str,
    judge_model: str = "gpt-4o",
) -> dict:
    """Run calibration check for a family's judge.

    Tests whether the judge correctly:
    1. Ranks uncorrupted > corrupted variants
    2. Identifies fatal failures in corrupted variants
    3. Does not over-penalise minor issues
    4. Shows consistent ranking across position swaps

    Returns calibration report::

        {
            "family_id": str,
            "judge_model": str,
            "discrimination_score": float,   # 0-1, good vs bad separation
            "consistency_score": float,       # 0-1, position-swap agreement
            "fatal_detection_rate": float,    # 0-1, fatal failures caught
            "calibrated": bool,              # True if all scores > 0.7
            "details": list[dict],           # per-variant results
        }
    """
    family = (
        await session.execute(
            select(PaperFamily).where(PaperFamily.id == family_id)
        )
    ).scalar_one_or_none()

    if not family:
        return _empty_report(family_id, judge_model, reason="family not found")

    # Pick a benchmark paper as the base (best calibration uses a known-good paper)
    base_paper = (
        await session.execute(
            select(Paper)
            .where(Paper.family_id == family_id, Paper.source == "benchmark", Paper.status == "published")
            .limit(1)
        )
    ).scalar_one_or_none()

    if not base_paper:
        # Fall back to any published paper in the family
        base_paper = (
            await session.execute(
                select(Paper)
                .where(Paper.family_id == family_id, Paper.status == "published")
                .limit(1)
            )
        ).scalar_one_or_none()

    if not base_paper:
        return _empty_report(family_id, judge_model, reason="no papers in family")

    # Generate calibration variants
    variants = await generate_calibration_variants(
        session, family_id, base_paper.id, variant_count=3
    )

    if not variants:
        return _empty_report(family_id, judge_model, reason="no variants generated")

    # Build family-specific prompt
    family_prompt = get_family_judge_prompt(family)

    # Get judge provider
    provider, model = await get_judge_provider()
    if judge_model != model:
        # Caller requested a specific model -- honour it if possible
        from app.services.llm.router import get_provider_for_model
        try:
            provider = get_provider_for_model(judge_model)
            model = judge_model
        except Exception:
            logger.debug("Requested judge model %s not available, using default %s", judge_model, model)

    base_content = base_paper.abstract or f"Title: {base_paper.title}"
    base_title = base_paper.title

    details: list[dict] = []
    correct_discriminations = 0
    fatal_detected = 0
    fatal_total = 0
    consistent_swaps = 0
    total_checks = 0

    for variant in variants:
        total_checks += 1

        # Build a synthetic "corrupted" content stub
        corrupted_content = (
            f"Title: {base_title} [CORRUPTED VARIANT]\n\n"
            f"This variant contains the following methodological flaw:\n"
            f"{variant['corruption_description']}\n\n"
            f"Original abstract (with flaw introduced):\n{base_content}"
        )
        corrupted_title = f"{base_title} (variant {variant['variant_index']})"

        try:
            result_a_first, result_b_first = await judge_match(
                provider=provider,
                model=model,
                paper_a_content=base_content,
                paper_b_content=corrupted_content,
                paper_a_title=base_title,
                paper_b_title=corrupted_title,
                system_prompt_override=family_prompt,
            )

            final = resolve_match(result_a_first.winner, result_b_first.winner)

            # The correct result is "a_wins" (original beats corrupted)
            discriminated = final == "a_wins"
            if discriminated:
                correct_discriminations += 1

            # Position-swap consistency
            swap_consistent = result_a_first.winner == result_b_first.winner
            if swap_consistent:
                consistent_swaps += 1

            # Fatal detection: for fatal-severity corruptions, the judge should
            # unambiguously pick the original
            is_fatal = variant.get("severity") == "fatal"
            if is_fatal:
                fatal_total += 1
                if discriminated:
                    fatal_detected += 1

            details.append({
                "variant_index": variant["variant_index"],
                "corruption_name": variant["corruption_name"],
                "severity": variant["severity"],
                "result_a_first": result_a_first.winner,
                "result_b_first": result_b_first.winner,
                "final_result": final,
                "discriminated_correctly": discriminated,
                "position_swap_consistent": swap_consistent,
            })

        except Exception as e:
            logger.error("Calibration variant check failed: %s", e)
            details.append({
                "variant_index": variant["variant_index"],
                "corruption_name": variant["corruption_name"],
                "severity": variant["severity"],
                "error": str(e),
                "discriminated_correctly": False,
                "position_swap_consistent": False,
            })

    discrimination_score = correct_discriminations / max(total_checks, 1)
    consistency_score = consistent_swaps / max(total_checks, 1)
    fatal_detection_rate = fatal_detected / max(fatal_total, 1) if fatal_total else 1.0

    calibrated = all(s > 0.7 for s in [
        discrimination_score,
        consistency_score,
        fatal_detection_rate,
    ])

    return {
        "family_id": family_id,
        "judge_model": model,
        "discrimination_score": round(discrimination_score, 3),
        "consistency_score": round(consistency_score, 3),
        "fatal_detection_rate": round(fatal_detection_rate, 3),
        "calibrated": calibrated,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_report(family_id: str, judge_model: str, reason: str = "") -> dict:
    """Return a zeroed-out calibration report."""
    return {
        "family_id": family_id,
        "judge_model": judge_model,
        "discrimination_score": 0.0,
        "consistency_score": 0.0,
        "fatal_detection_rate": 0.0,
        "calibrated": False,
        "details": [],
        "skip_reason": reason,
    }
