"""Cohort tags: tracks which model/config era produced each paper."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CohortTag(Base):
    __tablename__ = "cohort_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), unique=True, nullable=False)
    cohort_id: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "2026-Q2-opus4"
    generation_model: Mapped[str] = mapped_column(String(128), nullable=False)
    review_models_json: Mapped[str | None] = mapped_column(Text)  # JSON array
    tournament_judge_model: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
