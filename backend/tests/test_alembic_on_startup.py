"""Regression test: lifespan ensures new column-additions reach the
existing production schema.

Background: PR #37 added ``papers.last_heartbeat_at`` and
``papers.last_heartbeat_stage`` columns. Production deploy used
``Base.metadata.create_all`` (which creates new tables but never
ALTERs existing ones), so the new Paper columns never landed.
``GET /papers/{id}`` returned 500 because the ORM tried to query
columns that didn't exist.

The first attempt (``alembic upgrade head``) failed because the
initial migration tries to ``create_index`` on indexes that
``metadata.create_all`` already made. Until we untangle that, use
the simpler ``ensure_added_columns`` path that adds the missing
columns via raw SQL with ``IF NOT EXISTS``.
"""

from __future__ import annotations

import inspect


def test_lifespan_calls_ensure_added_columns():
    """The lifespan must call ``_ensure_added_columns`` after init_db
    so newly-added columns reach the production schema.
    """
    from app.main import lifespan

    src = inspect.getsource(lifespan)
    assert "_ensure_added_columns" in src, (
        "lifespan must call _ensure_added_columns after init_db so "
        "new columns reach existing tables (create_all doesn't ALTER)."
    )


def test_ensure_added_columns_handles_postgres_and_sqlite():
    """The helper must handle both dialects:
    - Postgres: ALTER TABLE ... ADD COLUMN IF NOT EXISTS
    - SQLite (test): no-op (tests create fresh schema each run)
    """
    from app.main import _ensure_added_columns

    src = inspect.getsource(_ensure_added_columns)
    assert "ADD COLUMN IF NOT EXISTS" in src, (
        "Must use IF NOT EXISTS so the helper is idempotent."
    )
    assert "last_heartbeat_at" in src, "Must add papers.last_heartbeat_at."
    assert "last_heartbeat_stage" in src, "Must add papers.last_heartbeat_stage."
    assert "sqlite" in src.lower(), "Must short-circuit for SQLite (test envs use it)."
