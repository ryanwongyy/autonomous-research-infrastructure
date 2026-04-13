"""Reliability metrics: tracked thresholds for paper and family quality.

Metrics include: replication_rate, manifest_fidelity, expert_score,
benchmark_percentile, correction_rate.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReliabilityMetric(Base):
    __tablename__ = "reliability_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("papers.id"), index=True)
    family_id: Mapped[str | None] = mapped_column(String(8), ForeignKey("paper_families.id"), index=True)
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False)  # replication_rate, manifest_fidelity, expert_score, benchmark_percentile, correction_rate
    value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float)
    passes_threshold: Mapped[bool] = mapped_column(Boolean, default=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    details_json: Mapped[str | None] = mapped_column(Text)
