"""Service for creating and retrieving significance memos."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rating import Rating
from app.models.significance_memo import SignificanceMemo

logger = logging.getLogger(__name__)


async def create_memo(
    session: AsyncSession,
    paper_id: str,
    author: str,
    memo_text: str,
    editorial_verdict: str,
) -> SignificanceMemo:
    """Create a significance memo with a snapshot of current tournament state.

    Args:
        session: Database session.
        paper_id: The paper this memo is for.
        author: Human name of the memo author.
        memo_text: The editorial reasoning.
        editorial_verdict: One of 'submit', 'hold', 'kill'.

    Returns:
        The created SignificanceMemo.
    """
    if editorial_verdict not in ("submit", "hold", "kill"):
        raise ValueError(f"Invalid verdict '{editorial_verdict}'. Must be submit/hold/kill.")

    # Snapshot current tournament state
    result = await session.execute(select(Rating).where(Rating.paper_id == paper_id))
    rating = result.scalar_one_or_none()

    rank_at_time = None
    confidence_json = None

    if rating:
        rank_at_time = rating.rank
        ci_lower = (
            rating.confidence_lower
            if rating.confidence_lower is not None
            else rating.mu - 1.96 * rating.sigma
        )
        ci_upper = (
            rating.confidence_upper
            if rating.confidence_upper is not None
            else rating.mu + 1.96 * rating.sigma
        )
        confidence_json = json.dumps(
            {
                "mu": round(rating.mu, 2),
                "sigma": round(rating.sigma, 2),
                "conservative_rating": round(rating.conservative_rating, 2),
                "lower": round(ci_lower, 2),
                "upper": round(ci_upper, 2),
                "matches_played": rating.matches_played,
            }
        )

    memo = SignificanceMemo(
        paper_id=paper_id,
        author=author,
        memo_text=memo_text,
        tournament_rank_at_time=rank_at_time,
        tournament_confidence_json=confidence_json,
        editorial_verdict=editorial_verdict,
    )
    session.add(memo)
    await session.flush()

    logger.info(
        "Created significance memo for paper %s: verdict=%s, author=%s, rank=%s",
        paper_id,
        editorial_verdict,
        author,
        rank_at_time,
    )
    return memo


async def get_memo_for_paper(session: AsyncSession, paper_id: str) -> SignificanceMemo | None:
    """Get the most recent significance memo for a paper."""
    result = await session.execute(
        select(SignificanceMemo)
        .where(SignificanceMemo.paper_id == paper_id)
        .order_by(SignificanceMemo.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
