"""Submission outcomes: tracks what happens after papers are submitted to venues."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SubmissionOutcome(Base):
    __tablename__ = "submission_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), nullable=False, index=True)
    venue_name: Mapped[str] = mapped_column(String(256), nullable=False)
    submitted_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decision: Mapped[str | None] = mapped_column(String(32))  # desk_reject / r_and_r / accepted / rejected
    decision_date: Mapped[datetime | None] = mapped_column(DateTime)
    revision_rounds: Mapped[int] = mapped_column(Integer, default=0)
    reviewer_feedback_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
