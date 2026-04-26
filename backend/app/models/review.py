from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # l1_structural, l2_provenance, l3_method, l4_adversarial, l5_human
    model_used: Mapped[str] = mapped_column(String(128), nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)  # pass, fail, revision_needed
    content: Mapped[str] = mapped_column(Text, nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info, warning, critical
    resolution_status: Mapped[str] = mapped_column(String(16), default="open")  # open, resolved, escalated, dismissed
    family_id: Mapped[str | None] = mapped_column(String(8), ForeignKey("paper_families.id"), index=True)  # for family-specific rubric tracking
    review_rubric_version: Mapped[str | None] = mapped_column(String(32))  # which version of the rubric was used
    issues_json: Mapped[str | None] = mapped_column(Text)  # JSON array of machine-readable issues
    resolution_notes: Mapped[str | None] = mapped_column(Text)  # how issues were resolved
    policy_scores_json: Mapped[str | None] = mapped_column(Text)  # JSON: {actionability, specificity, evidence_strength, stakeholder_relevance, implementation_feasibility}
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped[Paper] = relationship(back_populates="reviews")
    family: Mapped[PaperFamily | None] = relationship(lazy="joined")
