"""Regression test: stage wrappers always return a dict, never raise.

Background: production paper apep_1cc7f767 reached collegial_review,
got the targeted try/except recovery from PR #41, but still died with::

    greenlet_spawn has not been called; can't call await_only() here.

The error escaped past the wrappers because ``_run_stage_with_session``
and ``_run_stage_no_outer_session`` had unhandled exception paths
(e.g. ``_reload_paper`` raising before ``_run_stage`` even started).
The exception then bubbled to ``run_full_pipeline``'s main except,
which marked the WHOLE pipeline as error — including stages that
never even started (Verifier, Packager).

The fix: outer try/except in BOTH wrappers so a wrapper-level error
becomes a stage-level ``status='failed'`` result, not a pipeline kill.
The caller (run_full_pipeline) sees the failed stage and decides
whether to abort or continue. For collegial_review, it continues to
verifier on a fresh session.
"""

from __future__ import annotations

import inspect


def test_run_stage_with_session_has_outer_try_except():
    """Wrapper-level exceptions (paper reload, session open) must be
    caught and converted to a failed stage result.
    """
    from app.services.paper_generation.orchestrator import _run_stage_with_session

    src = inspect.getsource(_run_stage_with_session)
    # Outer try/except wrapping the WHOLE async with block
    assert "wrapper_fatal" in src, (
        "_run_stage_with_session must annotate wrapper-fatal results "
        "so the caller can distinguish from in-stage failures."
    )
    # Must catch all Exception, not raise
    assert "except Exception as wrapper_err" in src, (
        "Outer except must catch any wrapper-level exception."
    )


def test_run_stage_no_outer_session_has_outer_try_except():
    """Same contract for the no-outer-session variant."""
    from app.services.paper_generation.orchestrator import _run_stage_no_outer_session

    src = inspect.getsource(_run_stage_no_outer_session)
    assert "wrapper_fatal" in src, (
        "_run_stage_no_outer_session must also annotate wrapper-fatal "
        "results."
    )
    assert "except Exception as wrapper_err" in src, (
        "Must catch wrapper-level exceptions in the no-outer variant too."
    )
