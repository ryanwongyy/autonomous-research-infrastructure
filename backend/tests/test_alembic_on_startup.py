"""Regression test: lifespan runs alembic upgrade head on every boot.

Background: PR #37 added ``papers.last_heartbeat_at`` and ``papers.last_heartbeat_stage``
columns + a ``pipeline_runs`` table via Alembic migration ``a1f2c3d4e5b6``.
Production deploy used ``Base.metadata.create_all`` (which creates new
tables but never ALTERs existing ones), so the new Paper columns never
landed in the live schema. ``GET /papers/{id}`` returned 500 because
the ORM tried to query a column that didn't exist.

This test guards the contract: lifespan must run ``alembic upgrade head``
on every boot so future column-adding migrations also land automatically.
"""

from __future__ import annotations

import inspect


def test_lifespan_calls_alembic_upgrade():
    """The lifespan must reference ``_run_alembic_upgrade`` so columns
    added in later migrations reach production.
    """
    from app.main import lifespan

    src = inspect.getsource(lifespan)
    assert "_run_alembic_upgrade" in src, (
        "lifespan must call _run_alembic_upgrade after init_db so "
        "column-adding migrations actually land in production."
    )


def test_alembic_helper_uses_subprocess():
    """``_run_alembic_upgrade`` must use a subprocess so its own
    asyncio.run() inside alembic/env.py doesn't conflict with the
    already-running FastAPI event loop.
    """
    from app.main import _run_alembic_upgrade

    src = inspect.getsource(_run_alembic_upgrade)
    assert "asyncio.create_subprocess_exec" in src or "subprocess" in src, (
        "_run_alembic_upgrade must run alembic in a subprocess; "
        "in-process invocation hits 'asyncio.run() cannot be called "
        "from a running event loop'."
    )
    # Must run alembic upgrade head specifically
    assert '"upgrade"' in src and '"head"' in src, (
        "_run_alembic_upgrade must call ``alembic upgrade head``."
    )
