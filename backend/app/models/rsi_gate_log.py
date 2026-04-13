"""RSI Gate Log model -- records gate decisions (promotion, rollback, shadow eval,
A/B eval) for RSI experiments with before/after metrics and thresholds."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RSIGateLog(Base):
    __tablename__ = "rsi_gate_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(Integer, ForeignKey("rsi_experiments.id"), index=True)
    gate_type: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(16))
    metric_before_json: Mapped[str | None] = mapped_column(Text)
    metric_after_json: Mapped[str | None] = mapped_column(Text)
    threshold_json: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)
