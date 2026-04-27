"""LLM spend tracking and budget enforcement.

Step 5 of the "real data, real claims" plan. Two responsibilities:

  1. **Recording**: ``record_spend`` inserts an ``LLMSpend`` row for a single
     LLM call given the input/output token counts and the model. Cost in USD
     is computed from a pricing table per model.

  2. **Enforcement**: ``assert_paper_within_budget`` and
     ``assert_daily_within_budget`` raise ``BudgetExceededError`` when the
     caller would push spend past the configured caps. Batch endpoints use
     these as preconditions: a paper that has already burned its per-paper
     cap won't be allowed to start another generation pass.

The pricing table is intentionally a small dict in code rather than a
config file — wrong prices are a numeric bug, not a configuration mistake,
and will be caught by the unit tests below.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.llm_spend import LLMSpend

logger = logging.getLogger(__name__)


class BudgetExceededError(RuntimeError):
    """Raised when a budget cap is reached.

    The orchestrator and the batch endpoints catch this and treat it as a
    pipeline failure, NOT a transient error — retrying without operator
    intervention will only reach the same cap again.
    """


# ---------------------------------------------------------------------------
# Pricing table: USD per million tokens (input, output).
# Sourced from public list prices as of 2026-04. Prices that have been
# announced but not yet observed in production are marked with a `~`. When in
# doubt, prefer the higher number — the cost cap should err toward
# conservative.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float  # USD per 1,000,000 input tokens
    output_per_mtok: float  # USD per 1,000,000 output tokens


_PRICING: dict[str, ModelPrice] = {
    # Anthropic
    "claude-opus-4-6": ModelPrice(15.0, 75.0),
    "claude-opus-4-7": ModelPrice(15.0, 75.0),
    "claude-sonnet-4-6": ModelPrice(3.0, 15.0),
    "claude-haiku-4-6": ModelPrice(0.80, 4.0),
    # OpenAI
    "gpt-4o": ModelPrice(2.50, 10.0),
    "gpt-4o-mini": ModelPrice(0.15, 0.60),
    "o1": ModelPrice(15.0, 60.0),
    "o1-mini": ModelPrice(3.0, 12.0),
    # Google
    "gemini-1.5-pro": ModelPrice(1.25, 5.0),
    "gemini-1.5-flash": ModelPrice(0.075, 0.30),
}

# Conservative fallback price for unknown models — chosen to be on the
# expensive side so unrecognised models don't sneak past budget caps.
_UNKNOWN_MODEL_FALLBACK = ModelPrice(15.0, 75.0)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return USD cost for a single LLM call given the model + token counts.

    Unknown models use ``_UNKNOWN_MODEL_FALLBACK`` and emit a single warning
    log so the operator knows the cost is an upper-bound estimate.
    """
    price = _PRICING.get(model)
    if price is None:
        logger.warning(
            "cost_usd: unknown model %r — using conservative fallback "
            "(input=$%.2f/Mtok, output=$%.2f/Mtok). Add to _PRICING for "
            "accurate accounting.",
            model,
            _UNKNOWN_MODEL_FALLBACK.input_per_mtok,
            _UNKNOWN_MODEL_FALLBACK.output_per_mtok,
        )
        price = _UNKNOWN_MODEL_FALLBACK

    return (
        input_tokens * price.input_per_mtok / 1_000_000.0
        + output_tokens * price.output_per_mtok / 1_000_000.0
    )


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


async def record_spend(
    session: AsyncSession,
    *,
    paper_id: str | None,
    role: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    note: str | None = None,
) -> LLMSpend:
    """Insert one ``LLMSpend`` row for an LLM call.

    Returns the persisted row (with ``id`` and ``cost_usd`` populated). The
    caller decides whether to flush/commit; this helper does ``flush()`` so
    aggregate queries within the same transaction see the new row.
    """
    spend = LLMSpend(
        paper_id=paper_id,
        role=role,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd(model, input_tokens, output_tokens),
        note=note,
    )
    session.add(spend)
    await session.flush()
    return spend


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


async def paper_spend_total(session: AsyncSession, paper_id: str) -> float:
    """Sum ``cost_usd`` over all LLMSpend rows for one paper. Returns 0.0
    if there are none."""
    stmt = select(func.coalesce(func.sum(LLMSpend.cost_usd), 0.0)).where(
        LLMSpend.paper_id == paper_id
    )
    return float((await session.execute(stmt)).scalar_one())


async def daily_spend_total(session: AsyncSession) -> float:
    """Sum ``cost_usd`` over the last 24 hours, regardless of paper."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    stmt = select(func.coalesce(func.sum(LLMSpend.cost_usd), 0.0)).where(
        LLMSpend.created_at >= cutoff
    )
    return float((await session.execute(stmt)).scalar_one())


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------


async def assert_paper_within_budget(session: AsyncSession, paper_id: str) -> None:
    """Raise BudgetExceededError if the paper has already hit its per-paper cap.

    No-op when ``settings.cost_tracking_enabled`` is False or the cap is set
    to 0 (≈ disabled).
    """
    if not settings.cost_tracking_enabled:
        return
    cap = settings.max_spend_per_paper_usd
    if cap <= 0:
        return

    spent = await paper_spend_total(session, paper_id)
    if spent >= cap:
        raise BudgetExceededError(
            f"Paper {paper_id} has already spent ${spent:.2f}, "
            f"which is at or above the per-paper cap of ${cap:.2f}. "
            f"Refusing to dispatch further LLM calls. "
            f"Adjust MAX_SPEND_PER_PAPER_USD or kill the paper."
        )


async def assert_daily_within_budget(session: AsyncSession) -> None:
    """Raise BudgetExceededError if the rolling 24h spend has hit the daily cap.

    No-op when ``cost_tracking_enabled`` is False or the cap is 0.
    """
    if not settings.cost_tracking_enabled:
        return
    cap = settings.max_daily_spend_usd
    if cap <= 0:
        return

    spent = await daily_spend_total(session)
    if spent >= cap:
        raise BudgetExceededError(
            f"Rolling 24h LLM spend is ${spent:.2f}, "
            f"which is at or above the daily cap of ${cap:.2f}. "
            f"Refusing to start new pipeline work. "
            f"Adjust MAX_DAILY_SPEND_USD or wait for the window to roll forward."
        )
