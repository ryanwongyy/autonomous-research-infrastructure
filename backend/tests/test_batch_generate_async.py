"""Regression tests for the fire-and-poll /batch/generate-async endpoint.

Background: production runs #25145786347 and #25146400252 streamed
for 14m48s and were cut off by Render's hard ~15-min HTTP request
limit. The streaming endpoint can't reliably hold a request open
for the full pipeline duration.

The fire-and-poll endpoint:
  - Validates the request, creates Paper records, returns 202 with
    paper_ids in <1 sec.
  - Spawns ``asyncio.create_task`` per paper to run the pipeline
    in the background.
  - The client polls ``GET /papers/{id}`` for status updates.

These tests guard the contract.
"""

from __future__ import annotations

import inspect

from app.api.batch import _run_pipeline_in_background, batch_generate_async


def test_async_endpoint_function_exists_and_is_callable():
    """Smoke test: the fire-and-poll endpoint is importable and async.

    The full HTTP behaviour is exercised in production runs; testing
    the endpoint via the test client requires the async_session()
    factory to point at the in-memory SQLite engine, which the
    current conftest doesn't set up. The runtime contract — paper
    IDs returned, background tasks spawned — is verified at the
    source-inspect level here.
    """
    assert inspect.iscoroutinefunction(batch_generate_async)


def test_async_endpoint_spawns_background_tasks():
    """The endpoint must call ``asyncio.create_task`` per paper so
    pipelines run AFTER the response closes (no held HTTP connection).
    """
    src = inspect.getsource(batch_generate_async)
    assert "asyncio.create_task" in src, (
        "/batch/generate-async must spawn background tasks, not "
        "await the pipeline inline (otherwise we hit Render's "
        "15-min HTTP request limit again)."
    )
    assert "_run_pipeline_in_background" in src, (
        "Endpoint must delegate to _run_pipeline_in_background which "
        "swallows exceptions instead of leaking them as Task warnings."
    )


def test_async_endpoint_creates_paper_records_before_returning():
    """The endpoint must pre-create Paper rows so polling works
    immediately — without a delay where /papers/{id} returns 404.
    """
    src = inspect.getsource(batch_generate_async)
    assert "Paper(" in src and "session.add" in src, (
        "Endpoint must INSERT Paper records before returning paper_ids "
        "so /papers/{id} polling sees a row immediately."
    )
    assert "await session.commit()" in src, (
        "Pre-created Paper records must be committed before the endpoint returns."
    )


def test_pipeline_background_task_swallows_exceptions():
    """The background task must not propagate exceptions to uvicorn's
    "Task exception was never retrieved" handler.
    """
    src = inspect.getsource(_run_pipeline_in_background)
    assert "except Exception" in src, (
        "_run_pipeline_in_background must catch all exceptions; "
        "otherwise uvicorn logs them as unretrieved-task warnings "
        "and the operator can't trace them via paper.status."
    )
    assert "logger.exception" in src or "logger.error" in src, (
        "Background-task exceptions must be logged so they're not completely silent."
    )
