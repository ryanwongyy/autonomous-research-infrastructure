from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper_family import PaperFamily


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournament_runs.id"), nullable=False, index=True
    )
    paper_a_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.id"), nullable=False, index=True
    )
    paper_b_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.id"), nullable=False, index=True
    )
    winner_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("papers.id"), index=True
    )  # NULL = draw
    judge_model: Mapped[str] = mapped_column(String(128), nullable=False)
    judge_prompt: Mapped[str | None] = mapped_column(Text)
    judgment_a_first: Mapped[str | None] = mapped_column(
        Text
    )  # Raw response with paper A shown first
    judgment_b_first: Mapped[str | None] = mapped_column(
        Text
    )  # Raw response with paper B shown first
    result_a_first: Mapped[str | None] = mapped_column(String(16))  # "a_wins", "b_wins", "draw"
    result_b_first: Mapped[str | None] = mapped_column(String(16))  # "a_wins", "b_wins", "draw"
    final_result: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # "a_wins", "b_wins", "draw"
    batch_number: Mapped[int] = mapped_column(Integer, nullable=False)
    mu_change_a: Mapped[float | None] = mapped_column(Float)
    mu_change_b: Mapped[float | None] = mapped_column(Float)
    elo_change_a: Mapped[float | None] = mapped_column(Float)
    elo_change_b: Mapped[float | None] = mapped_column(Float)
    family_id: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("paper_families.id"), index=True
    )  # matches are family-scoped
    integrity_penalty_a: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # paper A had integrity issue
    integrity_penalty_b: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # paper B had integrity issue
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    family: Mapped[PaperFamily | None] = relationship(back_populates="matches", lazy="joined")
