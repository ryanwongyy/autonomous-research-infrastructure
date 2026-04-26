"""Failure records: systematic classification of all pipeline failures."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FailureRecord(Base):
    __tablename__ = "failure_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("papers.id"), index=True)
    family_id: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("paper_families.id"), index=True
    )
    failure_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # data_error, logic_error, hallucination, causal_overreach, source_drift, design_violation, formatting, other
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # low, medium, high, critical
    detection_stage: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # l1_structural, l2_provenance, etc.
    root_cause_category: Mapped[str | None] = mapped_column(String(64))
    resolution: Mapped[str | None] = mapped_column(Text)
    corrective_action: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
