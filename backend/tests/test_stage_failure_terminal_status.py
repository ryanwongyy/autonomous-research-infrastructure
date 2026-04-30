"""Tests that a stage failure flips Paper.status to a terminal value.

Production paper apep_8dcbf99e: pipeline started at 14:47:59, Scout
heart-beat at 14:48:03, then silence for 45 min until the workflow
poll loop timed out. ``Paper.status`` stayed at ``"draft"``,
``funnel_stage="idea"`` — visible signs of a stage failure but the
external observers (cron, frontend) had no way to know it was
terminal.

Root cause: the orchestrator's ``if stage_report["status"] == "failed":``
branch sets ``report["final_status"] = "killed_at_<stage>"`` and returns,
but never updates the ``Paper`` row. PR #44 added the status flip on
*success* and *verifier-rejection* paths but missed the stage-failure
path entirely.

These tests use source inspection (matching test_orchestrator_paper_status.py)
because the orchestrator's helpers open their own ``async_session()``
against the production database, not the test fixture's in-memory DB.
"""

from __future__ import annotations

import inspect
import re

from app.services.paper_generation import orchestrator
from app.services.paper_generation.orchestrator import _set_killed_at_stage


# ── Helper exists with the right shape ───────────────────────────────────────


def test_helper_exists_and_is_async():
    assert hasattr(orchestrator, "_set_killed_at_stage")
    assert inspect.iscoroutinefunction(orchestrator._set_killed_at_stage)


def test_helper_signature_takes_stage_name_and_error():
    """Signature: (paper_id: str, stage_name: str, error: str | None) -> None"""
    sig = inspect.signature(_set_killed_at_stage)
    assert list(sig.parameters.keys()) == ["paper_id", "stage_name", "error"]


def test_helper_writes_terminal_paper_columns():
    """Source check: the helper sets status='killed', funnel_stage='killed',
    populates kill_reason, and uses the 'killed_at_<stage>' prefix."""
    src = inspect.getsource(_set_killed_at_stage)
    # Status flips
    assert 'status="killed"' in src, (
        "Helper must set status='killed' (terminal value the cron poll "
        "loop watches for)."
    )
    assert 'funnel_stage="killed"' in src
    # Kill-reason prefix
    assert 'killed_at_' in src
    assert "kill_reason" in src


def test_helper_truncates_long_errors():
    """Source check: the helper caps the error tail so a 5KB traceback
    can't bloat the kill_reason field."""
    src = inspect.getsource(_set_killed_at_stage)
    # Look for an error-slicing operation like error[:300] or error[:500].
    sliced = re.search(r"error\[:\s*\d+\s*\]", src)
    assert sliced is not None, (
        "Helper must slice the error string (e.g. error[:300]) so a "
        "long traceback doesn't bloat kill_reason."
    )


def test_helper_swallows_its_own_session_errors():
    """Like _set_error: the helper uses its own short-lived session
    and catches Exception inside, so a poisoned-pool failure doesn't
    cascade out and prevent the report from returning. Mirrors the
    pattern from _set_error."""
    src = inspect.getsource(_set_killed_at_stage)
    assert "try:" in src
    assert "except Exception" in src or "except:" in src


# ── run_full_pipeline calls the helper at every killed_at_X branch ───────────


def test_every_killed_at_branch_calls_helper():
    """The 5 stages with explicit failure branches (Scout, Designer,
    Data Steward, Analyst, Drafter) must each call ``_set_killed_at_stage``
    on the failure path. Otherwise the paper sits at status='draft'
    indefinitely and the cron poll loop times out at 45 min.

    We grep-search the source allowing for line-wrapped argument lists
    so a future ``black`` reformat doesn't break the test.
    """
    src = inspect.getsource(orchestrator.run_full_pipeline)
    expected_stages = ["scout", "designer", "data_steward", "analyst", "drafter"]
    for stage in expected_stages:
        marker = f'killed_at_{stage}"'
        assert marker in src, f"missing final_status marker for {stage}"
        # The helper call must reference the same stage name. Allow
        # whitespace/newlines between '(' and the args so multi-line
        # wraps still match.
        pattern = (
            r"_set_killed_at_stage\s*\(\s*paper_id\s*,\s*"
            rf'"{stage}"'
            r"\s*,"
        )
        assert re.search(pattern, src), (
            f"run_full_pipeline must call _set_killed_at_stage(paper_id, "
            f"'{stage}', ...) when the {stage} stage fails. Without it, "
            f"Paper.status stays at 'draft' and the cron polls forever."
        )


def test_killed_at_branches_pass_stage_error_string():
    """Each helper call passes ``stage_report.get('error')`` as the
    third arg so the kill_reason includes whatever exception text the
    wrapper captured. Without this, kill_reason would be just
    'killed_at_<stage>' with no diagnostic detail."""
    src = inspect.getsource(orchestrator.run_full_pipeline)
    # Every helper call should be followed (within the same call site)
    # by stage_report.get("error").
    pattern = re.compile(
        r"_set_killed_at_stage\s*\([^)]*stage_report\.get\(\s*[\"']error[\"']\s*\)",
        re.DOTALL,
    )
    matches = pattern.findall(src)
    # 5 stage failure branches × 1 call each = 5
    assert len(matches) >= 5, (
        f"Expected 5 helper calls passing stage_report.get('error') as "
        f"the error arg; found {len(matches)}."
    )
