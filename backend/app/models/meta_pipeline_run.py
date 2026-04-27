"""Meta Pipeline Run model -- tracks end-to-end runs of the RSI meta-pipeline
through observation, proposal, shadow running, evaluation, and promotion stages."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetaPipelineRun(Base):
    __tablename__ = "meta_pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32))
    observation_json: Mapped[str | None] = mapped_column(Text)
    proposals_json: Mapped[str | None] = mapped_column(Text)
    shadow_results_json: Mapped[str | None] = mapped_column(Text)
    promotion_decision: Mapped[str | None] = mapped_column(String(16))
    production_delta_json: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
