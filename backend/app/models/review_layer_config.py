"""Review Layer Config model -- configures each review layer (L1-L5 or custom)
per family with status, bypass conditions, shadow results, and effectiveness."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReviewLayerConfig(Base):
    __tablename__ = "review_layer_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    layer_name: Mapped[str] = mapped_column(String(32))
    family_id: Mapped[str | None] = mapped_column(String(8), ForeignKey("paper_families.id"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    bypass_condition_json: Mapped[str | None] = mapped_column(Text)
    shadow_results_json: Mapped[str | None] = mapped_column(Text)
    effectiveness_score: Mapped[float | None] = mapped_column(Float)
    experiment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rsi_experiments.id"), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
