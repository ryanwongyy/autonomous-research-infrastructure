"""Significance memo: human editorial sign-off for submission readiness.

A significance memo captures a human's explicit reasoning for why a paper
is worth submitting despite tournament results being a noisy signal.
Required before the candidate -> submitted release transition.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper


class SignificanceMemo(Base):
    __tablename__ = "significance_memos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.id"), nullable=False, index=True
    )
    author: Mapped[str] = mapped_column(String(128), nullable=False)  # Human name
    memo_text: Mapped[str] = mapped_column(Text, nullable=False)
    tournament_rank_at_time: Mapped[int | None] = mapped_column(Integer)
    tournament_confidence_json: Mapped[str | None] = mapped_column(
        Text
    )  # JSON: {lower, upper, mu, sigma}
    editorial_verdict: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # submit / hold / kill
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped[Paper] = relationship(lazy="joined")
