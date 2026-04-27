from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.paper import Paper
    from app.models.rating import Rating
    from app.models.tournament_run import TournamentRun


class PaperFamily(Base):
    __tablename__ = "paper_families"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)  # "F1" .. "F11"
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lock_protocol_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # JSON-encoded fields stored as Text
    canonical_questions: Mapped[str | None] = mapped_column(
        Text
    )  # JSON array of example research questions
    accepted_methods: Mapped[str | None] = mapped_column(Text)  # JSON array of accepted methods
    public_data_sources: Mapped[str | None] = mapped_column(
        Text
    )  # JSON array of source descriptions
    novelty_threshold: Mapped[str | None] = mapped_column(
        Text
    )  # description of what counts as novel
    venue_ladder: Mapped[str | None] = mapped_column(
        Text
    )  # JSON: {"flagship": [...], "elite_field": [...]}
    mandatory_checks: Mapped[str | None] = mapped_column(Text)  # JSON array of required checks
    fatal_failures: Mapped[str | None] = mapped_column(
        Text
    )  # JSON array of instant-kill conditions
    elite_ceiling: Mapped[str | None] = mapped_column(
        Text
    )  # description of what makes a paper truly elite
    benchmark_config: Mapped[str | None] = mapped_column(
        Text
    )  # JSON with benchmark corpus configuration
    review_rubric: Mapped[str | None] = mapped_column(
        Text
    )  # JSON with family-specific review criteria/weights
    max_portfolio_share: Mapped[float] = mapped_column(Float, default=0.33)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # One-to-many relationships — foreign_keys required because Paper has two FKs to paper_families
    papers: Mapped[list[Paper]] = relationship(
        back_populates="family", foreign_keys="[Paper.family_id]", lazy="selectin"
    )
    ratings: Mapped[list[Rating]] = relationship(back_populates="family", lazy="selectin")
    matches: Mapped[list[Match]] = relationship(back_populates="family", lazy="selectin")
    tournament_runs: Mapped[list[TournamentRun]] = relationship(
        back_populates="family", lazy="selectin"
    )
