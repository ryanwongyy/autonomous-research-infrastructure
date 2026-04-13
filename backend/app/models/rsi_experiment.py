"""RSI Experiment model -- tracks recursive self-improvement experiments
across tiers with lifecycle states from proposal through activation or rollback."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RSIExperiment(Base):
    __tablename__ = "rsi_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tier: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32))
    cohort_id: Mapped[str | None] = mapped_column(String(64))
    family_id: Mapped[str | None] = mapped_column(String(8), ForeignKey("paper_families.id"), index=True)
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime)
    config_snapshot_json: Mapped[str | None] = mapped_column(Text)
    result_summary_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
