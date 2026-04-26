"""External expert reviews: tracks validation by non-system experts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExpertReview(Base):
    __tablename__ = "expert_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), nullable=False, index=True)
    expert_name: Mapped[str] = mapped_column(String(256), nullable=False)
    affiliation: Mapped[str | None] = mapped_column(String(256))
    review_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    methodology_score: Mapped[int | None] = mapped_column(Integer)
    contribution_score: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    is_pre_submission: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
