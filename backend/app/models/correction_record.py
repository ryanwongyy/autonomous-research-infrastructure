"""Correction records: tracks post-publication errata, retractions, and updates."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CorrectionRecord(Base):
    __tablename__ = "correction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.id"), nullable=False, index=True
    )
    correction_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # erratum / retraction / update
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_claims_json: Mapped[str | None] = mapped_column(
        Text
    )  # JSON array of claim IDs or text
    corrected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
