from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.source_card import SourceCard


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_card_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_cards.id"), nullable=False, index=True
    )
    snapshot_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 of fetched content
    snapshot_path: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # path in content-addressed storage
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    record_count: Mapped[int | None] = mapped_column(Integer)  # number of records/documents fetched
    fetch_parameters: Mapped[str | None] = mapped_column(Text)  # JSON of query parameters used
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Provenance proof — JSON describing HOW this snapshot's content was
    # obtained. Populated by the data_steward role from the source client's
    # FetchResult.proof dict. A non-null value with proof_method="http" is
    # required by L2 Provenance for any claim that cites this snapshot.
    #
    # Shape:
    #   {
    #     "method": "http" | "placeholder" | "vcr",
    #     "request_url": "https://...",     # for http/vcr
    #     "response_status": 200,            # for http/vcr
    #     "response_hash": "<sha256-hex>",   # for http/vcr (raw body hash)
    #     "fetched_at": "2026-04-26T12:34:56Z",
    #     "fetched_via": "openalex_client_v1"
    #   }
    provenance_proof_json: Mapped[str | None] = mapped_column(Text)

    # Many-to-one back to SourceCard
    source_card: Mapped[SourceCard] = relationship(back_populates="snapshots")
