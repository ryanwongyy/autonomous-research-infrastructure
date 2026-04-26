from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper_family import PaperFamily


class TournamentRun(Base):
    __tablename__ = "tournament_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_matches: Mapped[int] = mapped_column(Integer, default=0)
    total_batches: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running, completed, failed
    family_id: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("paper_families.id"), index=True
    )  # tournament runs are now family-scoped
    papers_in_pool: Mapped[int] = mapped_column(Integer, default=0)  # how many papers were eligible
    benchmark_papers: Mapped[int] = mapped_column(
        Integer, default=0
    )  # how many were benchmark papers
    ai_papers: Mapped[int] = mapped_column(Integer, default=0)  # how many were AI-generated
    judge_calibration_score: Mapped[float | None] = mapped_column(Float)  # calibration check result

    family: Mapped[PaperFamily | None] = relationship(
        back_populates="tournament_runs", lazy="joined"
    )
