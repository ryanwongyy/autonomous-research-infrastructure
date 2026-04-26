from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.source_snapshot import SourceSnapshot


class SourceCard(Base):
    __tablename__ = "source_cards"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "federal_register"
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)  # base URL or API endpoint
    tier: Mapped[str] = mapped_column(String(1), nullable=False, index=True)  # "A", "B", "C"
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "government_registry"
    temporal_coverage: Mapped[str | None] = mapped_column(Text)  # JSON: {start_date, end_date, notes}
    geographic_coverage: Mapped[str | None] = mapped_column(Text)  # JSON array of jurisdictions
    update_frequency: Mapped[str | None] = mapped_column(String(64))  # "daily", "weekly", etc.
    access_method: Mapped[str] = mapped_column(String(32), nullable=False)  # "api", "bulk_download", etc.
    requires_key: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_basis: Mapped[str | None] = mapped_column(Text)  # license or terms summary
    canonical_unit: Mapped[str | None] = mapped_column(String(128))  # unit of analysis
    claim_permissions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array: what source CAN support
    claim_prohibitions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array: what source CANNOT support
    required_corroboration: Mapped[str | None] = mapped_column(Text)  # JSON: when corroboration is needed
    parse_method: Mapped[str | None] = mapped_column(String(64))  # "json_api", "html_extract", etc.
    content_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of most recent fetch
    fragility_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 (robust) to 1.0 (brittle)
    retention_policy: Mapped[str | None] = mapped_column(Text)  # how long snapshots are kept
    known_traps: Mapped[str | None] = mapped_column(Text)  # JSON array of known pitfalls
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # One-to-many relationship
    snapshots: Mapped[list[SourceSnapshot]] = relationship(back_populates="source_card", lazy="selectin")
