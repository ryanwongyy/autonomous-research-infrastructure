"""Per-paper autonomy cards: tracks which pipeline roles were human-supervised vs autonomous."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AutonomyCard(Base):
    __tablename__ = "autonomy_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), unique=True, nullable=False)
    role_autonomy_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: {"scout": "full_auto"/"supervised"/"human_driven", ...}
    human_intervention_points_json: Mapped[str | None] = mapped_column(Text)  # JSON array of {role, stage, description}
    overall_autonomy_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0-1.0
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
