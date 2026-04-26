"""Role Config model -- defines agent roles with inheritance, capabilities,
boundaries, and lifecycle states tied to RSI experiments and prompt versions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoleConfig(Base):
    __tablename__ = "role_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(String(64))
    parent_role: Mapped[str | None] = mapped_column(String(64))
    family_id: Mapped[str | None] = mapped_column(String(8), ForeignKey("paper_families.id"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    capabilities_json: Mapped[str | None] = mapped_column(Text)
    boundaries_json: Mapped[str | None] = mapped_column(Text)
    prerequisite_stages_json: Mapped[str | None] = mapped_column(Text)
    prompt_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("prompt_versions.id"), index=True)
    experiment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rsi_experiments.id"), index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
