"""Collegial Exchange model -- records a single turn in the collegial review
dialogue.  Each exchange captures who spoke (colleague or drafter), the
content of the message, and metadata about what section or claims are being
discussed."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CollegialExchange(Base):
    __tablename__ = "collegial_exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collegial_sessions.id"), nullable=False, index=True
    )
    colleague_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("colleague_profiles.id"), index=True
    )
    speaker_role: Mapped[str] = mapped_column(String(16), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    exchange_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_section: Mapped[str | None] = mapped_column(String(64))
    referenced_claims: Mapped[str | None] = mapped_column(Text)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
