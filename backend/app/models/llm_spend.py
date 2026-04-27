"""Per-call ledger of LLM token usage and cost.

Step 5 of the "real data, real claims" plan: before turning the autonomous
loop on with real data, we need to be able to see — and cap — what's being
spent. This table is the ledger.

Every call to an LLM provider that is instrumented (via the helpers in
``app.services.llm.spend``) inserts one row here. The orchestrator and the
batch endpoints query aggregates of this table to enforce per-paper and
per-day spend caps.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper


class LLMSpend(Base):
    __tablename__ = "llm_spend"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Paper this call was made on behalf of, if any. Calls made outside a
    # paper context (RSI tuning, judge calibration without a target) leave
    # this NULL — they still count against the daily cap.
    paper_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("papers.id"), index=True)

    # Pipeline role / system that initiated the call ("scout", "drafter",
    # "verifier", "l3_method", "judge", "collegial_review", "rsi_optimizer",
    # …). Free-form so new roles don't need a migration.
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Provider key matching app.services.llm — "anthropic", "openai", "google".
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)

    # Reported by the provider's response (or 0 if not available — better
    # than failing).
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cost in USD computed from the pricing table at the time of the call.
    # Stored as Float for portability across SQLite/Postgres; the absolute
    # precision required (>= $0.001) is well within float range.
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Optional free-form note — useful for diagnosing surprise spend
    # (e.g. "retry-3" or "max_tokens=16384 verifier prompt").
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped[Paper | None] = relationship(back_populates="llm_spend_entries")
