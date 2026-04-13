from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper


class ClaimMap(Base):
    __tablename__ = "claim_maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(64), ForeignKey("papers.id"), nullable=False, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "empirical", "doctrinal", "historical", "theoretical", "descriptive"
    source_card_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("source_cards.id"), index=True)  # NULL if linked to result object
    source_snapshot_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("source_snapshots.id"), index=True)
    source_span_ref: Mapped[str | None] = mapped_column(Text)  # JSON: {document_id, page, paragraph, span_start, span_end}
    result_object_ref: Mapped[str | None] = mapped_column(Text)  # JSON: {analysis_run_id, table, column, row}
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)  # "pending", "verified", "failed", "disputed"
    verified_by: Mapped[str | None] = mapped_column(String(128))  # model or human that verified
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped["Paper"] = relationship(back_populates="claim_maps")
