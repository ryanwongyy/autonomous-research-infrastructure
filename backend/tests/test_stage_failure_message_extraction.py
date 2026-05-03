"""Tests for PR #76: extract failure messages from both ``error`` and
``reason`` keys when killing a paper at a failed stage.

Production paper apep_c1502865 (autonomous-loop run 25291316046) was
killed at the Designer stage. Querying the API afterwards:
  status: killed
  funnel_stage: killed
  kill_reason: "killed_at_designer"   ← no diagnostic
  error_message: null

The Designer stage returned ``{"status": "failed", "reason": "Empty
design YAML"}``. The orchestrator's kill helper read
``stage_report.get("error")`` which was None, so the rich reason
never reached kill_reason. Operators saw only "killed_at_designer"
with no clue why.

Two stages report failures via ``error`` (the exception path in
_run_stage), four via ``reason`` (soft-failure validation paths in
the stage functions themselves). The orchestrator was reading only
``error``.

PR #76 adds ``_stage_failure_message`` that prefers ``error`` (richer
when set, includes class name) and falls back to ``reason``. All
five kill-call-sites now use this helper.

This file locks in:
  * Helper exists and prefers error over reason
  * Falls back to reason when error is missing
  * Returns None when both are missing (helper doesn't crash)
  * All five call-sites in run_full_pipeline use the helper
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.orchestrator import (
    _stage_failure_message,
    run_full_pipeline,
)


def test_helper_prefers_error_when_both_present():
    """When the stage report has both keys, error wins (it's richer
    and was set by _run_stage's exception handler)."""
    report = {"error": "RuntimeError: blew up", "reason": "soft fallback"}
    assert _stage_failure_message(report) == "RuntimeError: blew up"


def test_helper_falls_back_to_reason():
    """The Designer-style soft failure: only `reason` is set."""
    report = {"status": "failed", "reason": "Empty design YAML"}
    assert _stage_failure_message(report) == "Empty design YAML"


def test_helper_returns_none_when_both_missing():
    """A bare {status:failed} report — no diagnostic, but at least
    the helper doesn't crash. The kill_reason will be the bare
    `killed_at_<stage>` and the operator gets to inspect logs."""
    report = {"status": "failed"}
    assert _stage_failure_message(report) is None


def test_helper_returns_none_for_empty_error_string():
    """An empty `error` string should not be returned; fall through
    to `reason` if available."""
    report = {"error": "", "reason": "actual reason"}
    assert _stage_failure_message(report) == "actual reason"


def test_helper_returns_none_when_both_empty():
    """Defensive: both empty strings → None."""
    report = {"error": "", "reason": ""}
    assert _stage_failure_message(report) is None


def test_orchestrator_uses_helper_at_kill_sites():
    """Source check: every _set_killed_at_stage call site reads via
    the helper, not stage_report.get('error') directly. Without this
    the soft-failure reason gets dropped on the floor."""
    src = inspect.getsource(run_full_pipeline)
    # The old direct read must be gone.
    assert 'stage_report.get("error")' not in src, (
        "Orchestrator must not read stage_report.get('error') directly — "
        "use _stage_failure_message() to also catch soft-failure 'reason'."
    )
    # Helper must be referenced at least 5 times (one per stage kill site).
    helper_uses = src.count("_stage_failure_message(stage_report)")
    assert helper_uses >= 5, (
        f"Expected >=5 helper call sites (one per killable stage), got {helper_uses}."
    )


def test_helper_referenced_in_module():
    from app.services.paper_generation import orchestrator

    assert hasattr(orchestrator, "_stage_failure_message")


def test_helper_docstring_names_production_paper():
    """Future-self should be able to trace the rule to apep_c1502865."""
    assert "apep_c1502865" in (_stage_failure_message.__doc__ or "")
