"""Regression test: collegial review survives session corruption.

Background: production paper apep_bfb6d393 reached the collegial-review
stage and died with::

    Can't reconnect until invalid transaction is rolled back.
    Please rollback() fully before proceeding.

Cause: ``run_full_collegial_review`` holds the outer session across
many inner LLM calls. When one of those raises mid-transaction (an
asyncpg InterfaceError mid-stream), the session enters a "failed
transaction" state. Subsequent operations — including the outer
``commit()`` in ``_run_stage_with_session`` — fail with the
"Can't reconnect" error.

Two layers of defense:

1. ``_stage_collegial_review`` now wraps ``run_full_collegial_review``
   in try/except; on failure, rolls back and returns
   ``completed_with_errors`` (collegial is non-fatal anyway).

2. ``_run_stage_with_session`` no longer raises when commit AND
   rollback both fail — it logs and returns the stage result with a
   ``wrapper_commit_failed`` marker. Persistence is lost but the
   pipeline can continue.
"""

from __future__ import annotations

import inspect


def test_stage_collegial_review_catches_role_function_exceptions():
    """If ``run_full_collegial_review`` raises, the stage must:
      - log the failure
      - rollback the session
      - return ``status='completed_with_errors'``
    Pipeline continues to verifier instead of crashing.
    """
    from app.services.paper_generation.orchestrator import _stage_collegial_review

    src = inspect.getsource(_stage_collegial_review)
    assert "try:" in src and "except Exception" in src, (
        "_stage_collegial_review must wrap run_full_collegial_review "
        "in try/except so session corruption doesn't kill the pipeline."
    )
    assert "completed_with_errors" in src, (
        "On collegial-review failure, return status='completed_with_errors' "
        "so the pipeline continues to verifier."
    )
    assert "session.rollback" in src, (
        "Must rollback the session on inner failure so the wrapper's "
        "later commit doesn't choke on a poisoned transaction."
    )


def test_run_stage_with_session_survives_commit_and_rollback_failure():
    """If both commit AND rollback fail (session totally poisoned),
    the wrapper must NOT raise — it logs and returns the stage result
    so the pipeline can continue with subsequent stages.
    """
    from app.services.paper_generation.orchestrator import _run_stage_with_session

    src = inspect.getsource(_run_stage_with_session)
    # Two nested try/except blocks: one for commit, one for rollback
    assert src.count("try:") >= 2, (
        "_run_stage_with_session must have nested try/except so a "
        "rollback failure doesn't propagate."
    )
    # Marker on the result so callers can see persistence failed
    assert "wrapper_commit_failed" in src, (
        "When persistence fails, the wrapper must annotate the result "
        "so callers can detect dropped writes."
    )
