"""Acknowledgment Record model -- tracks individual colleague contributions
to a paper so that the acknowledgments section can credit each colleague
for their specific substantive input."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AcknowledgmentRecord(Base):
    __tablename__ = "acknowledgment_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), nullable=False, index=True)
    colleague_id: Mapped[int] = mapped_column(Integer, ForeignKey("colleague_profiles.id"), nullable=False, index=True)
    contribution_type: Mapped[str] = mapped_column(String(32), nullable=False)
    contribution_summary: Mapped[str] = mapped_column(Text, nullable=False)
    exchanges_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_suggestions: Mapped[int] = mapped_column(Integer, default=0)
    acknowledgment_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
