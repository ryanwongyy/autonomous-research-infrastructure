"""Regression tests for pipeline_runs persistence + heartbeat fields.

Issues C + D from the post-second-paper assessment:

  C. The orchestrator's in-memory ``report['stages']`` dict is lost
     when the pipeline returns. Persist a PipelineRun row per stage
     so post-mortems don't require GitHub Actions logs.

  D. Polling clients can't tell "task is stuck at Verifier" from
     "task crashed silently". Heartbeat field on Paper, updated at
     each stage, lets pollers detect stalls.
"""

from __future__ import annotations

import inspect

from app.models.paper import Paper
from app.models.pipeline_run import PipelineRun
from app.services.paper_generation import orchestrator

# ── Issue C: pipeline_runs ─────────────────────────────────────────────


def test_pipeline_run_model_exists_with_required_columns():
    """The PipelineRun model must have the columns post-mortems need."""
    expected = {
        "id",
        "paper_id",
        "stage_name",
        "status",
        "started_at",
        "finished_at",
        "duration_sec",
        "error_class",
        "error_message",
        "error_traceback",
        "details_json",
    }
    actual = {c.name for c in PipelineRun.__table__.columns}
    missing = expected - actual
    assert not missing, f"PipelineRun is missing columns: {missing}"


def test_orchestrator_persists_stage_runs():
    """The orchestrator's ``_run_stage`` must call ``_persist_stage_run``
    after each stage so the row gets a PipelineRun for post-mortems.
    """
    src = inspect.getsource(orchestrator._run_stage)
    assert "_persist_stage_run" in src, "_run_stage must persist a PipelineRun row for each stage."


def test_persist_stage_run_helper_exists_and_swallows_errors():
    """The persist helper must not raise, since DB write failures
    shouldn't kill the pipeline.
    """
    fn = orchestrator._persist_stage_run
    src = inspect.getsource(fn)
    assert "except Exception" in src, (
        "_persist_stage_run must catch all exceptions; persist "
        "failures shouldn't kill the pipeline."
    )
    assert "PipelineRun" in src
    assert "async with async_session()" in src


# ── Issue D: heartbeat ─────────────────────────────────────────────────


def test_paper_model_has_heartbeat_columns():
    """The Paper model must have ``last_heartbeat_at`` and
    ``last_heartbeat_stage`` so the orchestrator can update them
    and pollers can read them.
    """
    cols = {c.name for c in Paper.__table__.columns}
    assert "last_heartbeat_at" in cols
    assert "last_heartbeat_stage" in cols


def test_orchestrator_writes_heartbeat_per_stage():
    """The orchestrator's ``_run_stage`` must update the heartbeat
    BEFORE running the stage so pollers immediately see "task entered
    stage X".
    """
    src = inspect.getsource(orchestrator._run_stage)
    assert "_write_heartbeat" in src, (
        "_run_stage must call _write_heartbeat at the start of each stage."
    )


def test_write_heartbeat_helper_uses_short_session():
    """The heartbeat write must use a short-lived session so its
    failure doesn't taint the stage's main work.
    """
    fn = orchestrator._write_heartbeat
    src = inspect.getsource(fn)
    assert "async with async_session()" in src
    assert "except Exception" in src, "_write_heartbeat must catch its own exceptions."
    assert "last_heartbeat_at" in src
    assert "last_heartbeat_stage" in src


def test_paper_response_schema_exposes_heartbeat():
    """``PaperResponse`` must expose the heartbeat fields so polling
    clients can read them through ``GET /papers/{id}``.
    """
    from app.schemas.paper import PaperResponse, PaperWithRating

    assert "last_heartbeat_at" in PaperResponse.model_fields
    assert "last_heartbeat_stage" in PaperResponse.model_fields
    # Inherited via PaperWithRating
    assert "last_heartbeat_at" in PaperWithRating.model_fields


def test_pipeline_runs_alembic_migration_exists():
    """The migration file must exist so production schema gets the
    new columns + table on next deploy.
    """
    import os

    migrations_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "alembic",
        "versions",
    )
    files = os.listdir(migrations_dir)
    matches = [f for f in files if "pipeline_runs" in f.lower() and f.endswith(".py")]
    assert matches, (
        "Expected an Alembic migration file with 'pipeline_runs' in "
        "its name; production won't get the new schema without it."
    )
