"""Regression test for ``_reload_paper`` in the pipeline orchestrator.

Background: production run #25129536542 crashed at line 772 of
``orchestrator.py`` with::

    File "/app/app/services/paper_generation/orchestrator.py",
        line 772, in _reload_paper
        await session.expire_all()
    TypeError: object NoneType can't be used in 'await' expression

``AsyncSession.expire_all()`` is **synchronous** in SQLAlchemy 2.x —
it returns ``None``, not a coroutine. Awaiting it raises a TypeError.

This test exists to lock in the fix and prevent the bug from regressing.
It also covers the not-found path so the function's contract stays clear.
"""

from __future__ import annotations

import inspect

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.services.paper_generation.orchestrator import _reload_paper


def test_async_session_expire_all_is_sync():
    """Sanity-check our assumption: ``expire_all`` is sync, returns None.

    If a future SQLAlchemy release makes this async, this test will
    fail loudly so we know to revisit the orchestrator.
    """
    assert not inspect.iscoroutinefunction(AsyncSession.expire_all), (
        "SQLAlchemy AsyncSession.expire_all changed to a coroutine; "
        "the orchestrator's _reload_paper helper needs to await it again."
    )


@pytest.mark.asyncio
async def test_reload_paper_returns_paper(db_session: AsyncSession):
    """_reload_paper round-trips a real Paper without awaiting any None."""
    paper = Paper(
        id="apep_test01",
        title="Reload-paper test",
        source="ape",
        status="draft",
        review_status="awaiting",
        family_id="F1",
        funnel_stage="idea",
    )
    db_session.add(paper)
    await db_session.flush()

    reloaded = await _reload_paper(db_session, "apep_test01")
    assert reloaded.id == "apep_test01"
    assert reloaded.title == "Reload-paper test"


@pytest.mark.asyncio
async def test_reload_paper_raises_when_missing(db_session: AsyncSession):
    """_reload_paper raises ValueError for unknown IDs (caller-friendly)."""
    with pytest.raises(ValueError, match="not found during reload"):
        await _reload_paper(db_session, "apep_does_not_exist")
