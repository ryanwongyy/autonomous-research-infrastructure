from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DomainConfig(Base):
    __tablename__ = "domain_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    data_sources: Mapped[str | None] = mapped_column(Text)  # JSON array of API configs
    analysis_tool: Mapped[str] = mapped_column(String(32), default="python")  # "R" or "python"
    evaluation_criteria: Mapped[str | None] = mapped_column(
        Text
    )  # JSON: {rewards: [], penalties: []}
    review_models: Mapped[str | None] = mapped_column(Text)  # JSON: {stage: model_id}
    # Defaults are sensible-on-fresh-install ids; runtime calls go via
    # `app.services.llm.router` which reads `settings.<>_model` and can be
    # overridden per-deployment via env vars. `claude-opus-4-5` replaces
    # the previous `claude-opus-4-6` literal — that name was never a real
    # public Anthropic model id and caused 400 fast-fails in production.
    judge_model: Mapped[str] = mapped_column(String(128), default="gpt-4o")
    generation_model: Mapped[str] = mapped_column(String(128), default="claude-opus-4-5")
    categories: Mapped[str | None] = mapped_column(Text)  # JSON array of {slug, name}
    countries: Mapped[str | None] = mapped_column(Text)  # JSON array or null
    methods: Mapped[str | None] = mapped_column(Text)  # JSON array of method names
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
