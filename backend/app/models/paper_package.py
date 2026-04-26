from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper


class PaperPackage(Base):
    __tablename__ = "paper_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), unique=True, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 Merkle root of all artifacts
    package_path: Mapped[str] = mapped_column(Text, nullable=False)  # path in storage
    lock_artifact_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of frozen design
    source_manifest_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of source manifest
    code_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of analysis code
    result_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of result objects
    manuscript_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of final manuscript
    version_major: Mapped[int] = mapped_column(Integer, default=1)
    version_minor: Mapped[int] = mapped_column(Integer, default=0)
    version_patch: Mapped[int] = mapped_column(Integer, default=0)
    authorship_declaration: Mapped[str | None] = mapped_column(Text)  # JSON: human authors and contributions
    ai_contribution_log: Mapped[str | None] = mapped_column(Text)  # JSON: Claude's role at each pipeline stage
    disclosure_text: Mapped[str | None] = mapped_column(Text)  # standardized disclosure
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)

    paper: Mapped[Paper] = relationship(back_populates="package")
