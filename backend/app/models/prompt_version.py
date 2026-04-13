"""Prompt Version model -- versioned prompt texts for role prompts, review prompts,
judge prompts, and family configs, with optional linkage to RSI experiments."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_key: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    prompt_text: Mapped[str] = mapped_column(Text)
    diff_from_previous: Mapped[str | None] = mapped_column(Text)
    experiment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rsi_experiments.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    performance_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
