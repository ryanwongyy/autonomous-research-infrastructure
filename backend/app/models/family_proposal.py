"""Family Proposal model -- tracks proposals for new paper families derived
from clustering analysis, with viability scoring and approval workflow."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FamilyProposal(Base):
    __tablename__ = "family_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposed_name: Mapped[str] = mapped_column(String(256))
    proposed_short_name: Mapped[str] = mapped_column(String(64))
    proposed_description: Mapped[str | None] = mapped_column(Text)
    source_cluster_json: Mapped[str | None] = mapped_column(Text)
    kill_reasons_json: Mapped[str | None] = mapped_column(Text)
    estimated_viability_score: Mapped[float | None] = mapped_column(Float)
    experiment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("rsi_experiments.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))
    resulting_family_id: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
