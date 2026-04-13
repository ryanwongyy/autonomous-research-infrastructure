from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper


class LockArtifact(Base):
    __tablename__ = "lock_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), nullable=False, index=True)
    family_id: Mapped[str] = mapped_column(String(8), ForeignKey("paper_families.id"), nullable=False, index=True)
    lock_protocol_type: Mapped[str] = mapped_column(String(64), nullable=False)  # must match family's protocol
    version: Mapped[int] = mapped_column(Integer, default=1)  # major version; new version on substantive change
    lock_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of the lock YAML
    lock_yaml: Mapped[str] = mapped_column(Text, nullable=False)  # the actual frozen design YAML
    narrative_memo: Mapped[str | None] = mapped_column(Text)  # explanation of design choices
    source_manifest_hash: Mapped[str | None] = mapped_column(String(64))  # hash of source manifest at lock time
    immutable_fields: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of field names that cannot change
    mutable_fields: Mapped[str | None] = mapped_column(Text)  # JSON array of fields that may evolve
    locked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    locked_by: Mapped[str | None] = mapped_column(String(128))  # human who approved lock, or "system"
    superseded_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("lock_artifacts.id"), index=True)  # newer version
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    paper: Mapped["Paper"] = relationship(back_populates="lock_artifacts")
