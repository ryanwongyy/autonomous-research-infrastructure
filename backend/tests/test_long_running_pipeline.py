"""Regression tests for long-running-pipeline DB safety.

Background: production run #25132990123 ran for ~11 minutes and
crashed with::

    sqlalchemy.dialects.postgresql.asyncpg.InterfaceError:
    cannot call Transaction.rollback(): the underlying connection
    is closed.

Root cause: the orchestrator held a SINGLE long-running DB
transaction across all 8 pipeline stages (~10+ min) while LLMs
were thinking. Postgres' default ``idle_in_transaction_session_timeout``
killed the connection.

Fix is two-pronged:
  - app/database.py: set ``server_settings.idle_in_transaction_session_timeout=0``
    on Postgres connections so the timeout doesn't apply.
  - orchestrator.py: commit between stages so we don't hold one
    long-running transaction.

These tests guard both contracts.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation import orchestrator


def test_orchestrator_uses_per_stage_sessions():
    """Each pipeline stage must run in its OWN session lifecycle.

    Counts both helper variants:
      - _run_stage_with_session: short stages (<2 min)
      - _run_stage_no_outer_session: long-LLM stages, doesn't hold
        any session across the call
    """
    src = inspect.getsource(orchestrator.run_full_pipeline)
    helper_calls = src.count("_run_stage_with_session(") + src.count(
        "_run_stage_no_outer_session("
    )
    assert helper_calls >= 7, (
        f"Expected >=7 stage-helper calls in run_full_pipeline; got {helper_calls}."
    )

    short_src = inspect.getsource(orchestrator._run_stage_with_session)
    assert "async_session()" in short_src
    assert "await s.commit()" in short_src

    # _run_stage_no_outer_session: no session held across stage call
    long_src = inspect.getsource(orchestrator._run_stage_no_outer_session)
    assert "async_session()" in long_src
    # Marker: passes session=None to _run_stage so the stage manages
    # its own DB lifecycle.
    assert "None, paper" in long_src, (
        "_run_stage_no_outer_session must pass session=None so no "
        "session is held across the long LLM call."
    )


def test_long_llm_stages_routed_through_no_outer_session():
    """Analyst, Drafter, Verifier MUST use _run_stage_no_outer_session.

    These stages have LLM calls that take 1-5+ min. If routed through
    _run_stage_with_session, the outer session's connection dies during
    the LLM call (production runs #25133985204, #25135681422,
    #25136675659 all hit InterfaceError on the final commit).
    """
    src = inspect.getsource(orchestrator.run_full_pipeline)
    for stage_name in ("_stage_analyst", "_stage_drafter", "_stage_verifier"):
        # Find the helper call for this stage.
        # Pattern: `await _run_stage_X("name", _stage_X, ...)`
        idx = src.find(stage_name + ",")
        assert idx > 0, f"{stage_name} not found in run_full_pipeline"
        # Walk back to find which helper was called.
        # Look at the 200 chars before this stage_name reference.
        prefix = src[max(0, idx - 200) : idx]
        assert "_run_stage_no_outer_session(" in prefix, (
            f"{stage_name} must be routed through "
            f"_run_stage_no_outer_session(...) — it has long LLM calls "
            f"that drop the connection if a session is held across them."
        )


def test_database_url_disables_idle_in_tx_timeout_for_postgres():
    """When using Postgres, server_settings must include
    idle_in_transaction_session_timeout='0' so a long pipeline
    transaction isn't killed.

    SQLite skips this entire path (no server_settings concept).
    """
    from app.database import _engine_kwargs, _is_sqlite

    if _is_sqlite:
        # Test environment uses SQLite; the postgres-specific path
        # is exercised only in production. Verify config presence
        # at the source level instead.
        import app.database as db_module

        src = inspect.getsource(db_module)
        assert "idle_in_transaction_session_timeout" in src, (
            "Database module must configure "
            "idle_in_transaction_session_timeout for Postgres "
            "connections to avoid mid-pipeline disconnects."
        )
        return

    connect_args = _engine_kwargs.get("connect_args", {})
    server_settings = connect_args.get("server_settings", {})
    assert server_settings.get("idle_in_transaction_session_timeout") == "0", (
        "Postgres connections must disable the idle_in_transaction "
        "killer so the long paper-generation pipeline isn't dropped."
    )
