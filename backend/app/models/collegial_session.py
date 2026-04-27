"""Collegial Session model -- tracks a complete multi-turn collegial review
session for a paper, including which colleagues participated, the manuscript
snapshot at session start, exchange counts, incorporation statistics, and
convergence-loop quality tracking.

Status values:
  in_progress         — currently reviewing
  converged           — quality assessment says ready for submission
  max_rounds_reached  — hit the revision cap without converging
  plateaued           — quality scores stopped improving
  abandoned           — no feedback received
  completed           — legacy single-pass completion
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CollegialSession(Base):
    __tablename__ = "collegial_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    colleague_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    manuscript_snapshot: Mapped[str | None] = mapped_column(Text)
    total_exchanges: Mapped[int] = mapped_column(Integer, default=0)
    suggestions_accepted: Mapped[int] = mapped_column(Integer, default=0)
    suggestions_rejected: Mapped[int] = mapped_column(Integer, default=0)
    suggestions_partially_incorporated: Mapped[int] = mapped_column(Integer, default=0)
    session_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # ── Convergence-loop fields ──────────────────────────────────────
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    max_rounds: Mapped[int] = mapped_column(Integer, default=5)
    target_venue: Mapped[str | None] = mapped_column(String(256))
    # JSON array of per-round quality assessments:
    # [{"round": 1, "overall_score": 7.2, "verdict": "minor_revision", "dimensions": {...}}, ...]
    quality_trajectory_json: Mapped[str | None] = mapped_column(Text)
    final_quality_score: Mapped[float | None] = mapped_column(Float)
