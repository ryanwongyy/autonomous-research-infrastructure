"""Novelty checks: prevents derivative and near-duplicate papers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NoveltyCheck(Base):
    __tablename__ = "novelty_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), nullable=False, index=True)
    checked_against_count: Mapped[int] = mapped_column(Integer, default=0)
    highest_similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    similar_paper_ids_json: Mapped[str | None] = mapped_column(Text)  # JSON array
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # novel / marginal / derivative
    model_used: Mapped[str] = mapped_column(String(128), nullable=False)
    check_details_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
