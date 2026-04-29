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
    """Each pipeline stage must run in its OWN AsyncSession.

    A single AsyncSession holds one underlying connection until
    closed; if the connection is dropped mid-pipeline (e.g. after
    10+ minutes of LLM work), even ``commit()`` and ``rollback()``
    on the dead connection raise InterfaceError. The fix is per-stage
    sessions so each stage gets a fresh connection from the pool
    (with pool_pre_ping verifying it).

    This test counts ``_run_stage_with_session`` calls in
    run_full_pipeline. Should be at least 7 (one per major stage).
    """
    src = inspect.getsource(orchestrator.run_full_pipeline)
    helper_calls = src.count("_run_stage_with_session(")
    assert helper_calls >= 7, (
        f"Expected >=7 _run_stage_with_session() calls in "
        f"run_full_pipeline; got {helper_calls}. If stages share "
        f"a single session, the pipeline holds one connection across "
        f"all stages and drops dead at ~10 minutes."
    )

    helper_src = inspect.getsource(orchestrator._run_stage_with_session)
    assert "async_session()" in helper_src, (
        "_run_stage_with_session must open a fresh AsyncSession per "
        "stage so each call gets a fresh connection from the pool."
    )
    assert "await s.commit()" in helper_src, (
        "_run_stage_with_session must commit each stage's writes."
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
