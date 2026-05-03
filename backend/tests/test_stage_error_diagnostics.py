"""Regression tests: per-stage exception diagnostics.

Background: production run #25137481628 had Analyst raise an
exception with an empty ``str(e)``. The pipeline showed
``error_message: "(no error message)"`` — useless for debugging.

The fix: ``_run_stage`` now captures ``error_class`` and
``error_traceback`` alongside ``error``, and combines them into
``error: f"{type(e).__name__}: {str(e) or '(empty)'}"`` so even
bare exceptions surface something actionable.

These tests guard the contract.
"""

from __future__ import annotations

import inspect

import pytest

from app.services.paper_generation import orchestrator


def test_run_stage_sets_error_class_on_exception():
    """The ``_run_stage`` helper must include ``error_class`` and
    ``error_traceback`` on the failed result.
    """
    src = inspect.getsource(orchestrator._run_stage)
    assert "error_class" in src, (
        "_run_stage must capture error_class so empty-message "
        "exceptions still produce diagnostic output."
    )
    assert "error_traceback" in src, "_run_stage must capture error_traceback for stage failures."
    assert "type(e).__name__" in src, "_run_stage must derive error_class from the exception type."


@pytest.mark.asyncio
async def test_run_stage_handles_bare_exception():
    """A bare RuntimeError() with no message should produce a
    non-empty error string.
    """

    async def _bare_raise(session, paper, **_):
        raise RuntimeError()  # empty message

    class _FakePaper:
        id = "apep_test"

    result = await orchestrator._run_stage("scout", _bare_raise, None, _FakePaper())

    assert result["status"] == "failed"
    # Even with empty str(e), error must include the class name
    assert result["error_class"] == "RuntimeError"
    assert "RuntimeError" in result["error"]
    assert result["error_traceback"]
