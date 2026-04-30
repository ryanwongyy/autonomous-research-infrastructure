"""PipelineRun: persisted per-stage outcome of paper-generation pipelines.

The orchestrator's in-memory ``report['stages']`` dict is convenient for
inspecting a SINGLE run, but it's lost when the pipeline returns. To
diagnose why paper apep_28011bda took 28 min, or why apep_faf874ae
left 13/26 claims pending, we need persisted per-stage history.

Each row captures one stage of one paper's pipeline:
  - which stage it was (scout, designer, ..., packager)
  - status (completed, failed, completed_with_errors)
  - duration in seconds
  - error_class + error_message + error_traceback if it failed
  - started_at + finished_at timestamps

A paper's pipeline produces one PipelineRun row per stage it reached.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    stage_name: Mapped[str] = mapped_column(
        String(32), index=True
    )  # scout, designer, data_steward, analyst, drafter, collegial_review, verifier, packager
    status: Mapped[str] = mapped_column(
        String(32), index=True
    )  # completed, failed, completed_with_errors

    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_sec: Mapped[float | None] = mapped_column(Float)

    # Error info — populated when status == "failed"
    error_class: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_traceback: Mapped[str | None] = mapped_column(Text)

    # Free-form JSON blob for stage-specific details (e.g. Scout's
    # screening_results, Drafter's claim_count). Mirrors the
    # in-memory ``stage_details`` field surfaced via batch.py.
    details_json: Mapped[str | None] = mapped_column(Text)
