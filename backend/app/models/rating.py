from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.id"), unique=True, nullable=False
    )
    mu: Mapped[float] = mapped_column(Float, default=25.0)
    sigma: Mapped[float] = mapped_column(Float, default=8.333)
    conservative_rating: Mapped[float] = mapped_column(Float, default=0.0)  # mu - 3*sigma
    elo: Mapped[float] = mapped_column(Float, default=1500.0)
    matches_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[int | None] = mapped_column(Integer)
    rank_change_48h: Mapped[int] = mapped_column(Integer, default=0)
    confidence_lower: Mapped[float | None] = mapped_column(Float)  # mu - 1.96*sigma (95% CI)
    confidence_upper: Mapped[float | None] = mapped_column(Float)  # mu + 1.96*sigma (95% CI)
    family_id: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("paper_families.id"), index=True
    )  # ratings are family-scoped
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    paper: Mapped[Paper] = relationship(back_populates="rating")
    family: Mapped[PaperFamily | None] = relationship(back_populates="ratings", lazy="joined")
