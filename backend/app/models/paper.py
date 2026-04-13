from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.rating import Rating
    from app.models.review import Review
    from app.models.paper_family import PaperFamily
    from app.models.lock_artifact import LockArtifact
    from app.models.claim_map import ClaimMap
    from app.models.paper_package import PaperPackage


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # "ape", "aer", "aej_policy", "benchmark"
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    country: Mapped[str | None] = mapped_column(String(64))
    method: Mapped[str | None] = mapped_column(String(64))  # "DiD", "RDD", "IV", etc.
    version: Mapped[int] = mapped_column(Integer, default=1)
    family_id: Mapped[str | None] = mapped_column(String(8), ForeignKey("paper_families.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)  # draft, locked, analyzing, drafting, reviewing, revision, candidate, submitted, public, rejected, killed
    review_status: Mapped[str] = mapped_column(String(32), default="awaiting")  # awaiting, peer_reviewed, issues, errors
    paper_pdf_path: Mapped[str | None] = mapped_column(Text)
    paper_tex_path: Mapped[str | None] = mapped_column(Text)
    code_path: Mapped[str | None] = mapped_column(Text)
    data_path: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)  # JSON blob for domain-specific metadata
    lock_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of active lock artifact
    lock_version: Mapped[int] = mapped_column(Integer, default=0)  # current lock version (0 = not yet locked)
    lock_timestamp: Mapped[datetime | None] = mapped_column(DateTime)  # when design was locked
    release_status: Mapped[str] = mapped_column(String(32), default="internal", index=True)  # internal, candidate, submitted, public
    funnel_stage: Mapped[str] = mapped_column(String(32), default="idea", index=True)  # idea, screened, locked, ingesting, analyzing, drafting, reviewing, revision, benchmark, candidate, submitted, public, killed
    secondary_family_id: Mapped[str | None] = mapped_column(String(8), ForeignKey("paper_families.id"), index=True)  # optional secondary family
    idea_card_yaml: Mapped[str | None] = mapped_column(Text)  # the idea card YAML
    novelty_score: Mapped[float | None] = mapped_column(Float)  # 0-5 scale
    data_adequacy_score: Mapped[float | None] = mapped_column(Float)  # 0-5 scale
    venue_fit_score: Mapped[float | None] = mapped_column(Float)  # 0-5 scale
    overall_screening_score: Mapped[float | None] = mapped_column(Float)  # weighted composite
    kill_reason: Mapped[str | None] = mapped_column(Text)  # why this project was killed
    data_question_cluster: Mapped[str | None] = mapped_column(String(128))  # for salami-slicing prevention
    domain_config_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    rating: Mapped["Rating"] = relationship(back_populates="paper", uselist=False, lazy="joined")
    reviews: Mapped[list["Review"]] = relationship(back_populates="paper", lazy="selectin")
    family: Mapped["PaperFamily | None"] = relationship(back_populates="papers", foreign_keys=[family_id], lazy="joined")
    secondary_family: Mapped["PaperFamily | None"] = relationship(foreign_keys=[secondary_family_id], lazy="joined")
    lock_artifacts: Mapped[list["LockArtifact"]] = relationship(back_populates="paper", lazy="selectin")
    claim_maps: Mapped[list["ClaimMap"]] = relationship(back_populates="paper", lazy="selectin")
    package: Mapped["PaperPackage | None"] = relationship(back_populates="paper", uselist=False, lazy="joined")
