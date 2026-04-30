"""Add pipeline_runs table + Paper.last_heartbeat fields

Revision ID: a1f2c3d4e5b6
Revises: cdef8b8f700b
Create Date: 2026-04-30 04:30:00.000000

Two related changes:

1. ``pipeline_runs`` table — persisted per-stage outcome of paper-
   generation pipelines. Lets us answer "what stage did paper X die
   at?" and "how long did paper Y's Drafter take?" without backend
   log access. Diagnostic data already in the orchestrator's in-memory
   ``report['stages']`` dict, just persisted now.

2. ``papers.last_heartbeat_at`` + ``papers.last_heartbeat_stage`` —
   updated by the orchestrator at each stage. Polling clients use
   the heartbeat to detect stalled tasks (e.g. if last_heartbeat_at
   is >5 min ago, the background task is probably dead).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f2c3d4e5b6"
down_revision: str | None = "cdef8b8f700b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── pipeline_runs table ───────────────────────────────────────────
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "paper_id",
            sa.String(length=64),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_name", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("error_class", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_pipeline_runs_paper_id", "pipeline_runs", ["paper_id"], unique=False
    )
    op.create_index(
        "ix_pipeline_runs_stage_name",
        "pipeline_runs",
        ["stage_name"],
        unique=False,
    )
    op.create_index(
        "ix_pipeline_runs_status", "pipeline_runs", ["status"], unique=False
    )
    op.create_index(
        "ix_pipeline_runs_started_at",
        "pipeline_runs",
        ["started_at"],
        unique=False,
    )

    # ── papers heartbeat columns ──────────────────────────────────────
    op.add_column(
        "papers",
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "papers",
        sa.Column("last_heartbeat_stage", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("papers", "last_heartbeat_stage")
    op.drop_column("papers", "last_heartbeat_at")
    op.drop_index("ix_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_stage_name", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_paper_id", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
