"""Colleague Profile model -- defines specialized reviewer personas used in
the collegial review loop.  Each profile carries a unique perspective
(methodology, domain, venue strategy, etc.) and a system prompt that gives
the LLM its personality and focus."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ColleagueProfile(Base):
    __tablename__ = "colleague_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    expertise_area: Mapped[str] = mapped_column(String(64), nullable=False)
    perspective_description: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
