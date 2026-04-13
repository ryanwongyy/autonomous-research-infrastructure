"""Drift Threshold Log model -- captures adjustments to drift thresholds
per family, recording gate block rates and downstream failure rates."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DriftThresholdLog(Base):
    __tablename__ = "drift_threshold_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    family_id: Mapped[str | None] = mapped_column(String(8), ForeignKey("paper_families.id"), index=True)
    previous_threshold: Mapped[float] = mapped_column(Float)
    new_threshold: Mapped[float] = mapped_column(Float)
    gate_block_rate: Mapped[float] = mapped_column(Float)
    downstream_failure_rate: Mapped[float] = mapped_column(Float)
    experiment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rsi_experiments.id"), index=True)
    adjusted_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
