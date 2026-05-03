"""Tests for PR #75: review-pipeline reject + escalate paths set
terminal status so the orphan reaper leaves the paper alone.

Production paper apep_427ca0f1 (autonomous-loop run 25291316046)
went all the way through L1-L5 with PR #74 working. L4 returned
verdict=fail and L5 escalation triggered. The paper's final state
should have been "rejected" or similar terminal status — instead
it stayed at status="reviewing" because:

  - Two reject branches (L1 fail, L2 fail) set status="reviewing"
  - The L3+L4 fail branch also set status="reviewing"
  - The decision==reject branch also set status="reviewing"
  - The L5 escalate branch never called _set_paper_status at all,
    so status stayed at whatever was set on entry ("reviewing")

The orphan reaper (papers.py) kills any paper at non-terminal
status with stale heartbeat. The review pipeline never updates
heartbeat (only the generation orchestrator does), so every
"reviewing" paper hits stale-heartbeat in 30 min and gets reaped.

Net effect: NO paper could ever reach a stable terminal state
post-review. Pass papers became "candidate" (terminal) — fine.
But every rejected/escalated paper got status="reviewing" → reaped.

PR #75:
  - All 4 reject branches now set status="rejected" (terminal)
  - The L5 escalate branch sets status="rejected" with
    review_status="escalated" (preserves the human-review signal
    while marking the paper terminal so reaper leaves it alone)
  - "rejected" is in the orphan reaper's terminal_statuses tuple

This file locks in:
  * No reject branch sets status="reviewing"
  * All 4 reject branches set status="rejected"
  * Escalate branch sets status="rejected", review_status="escalated"
  * "rejected" is treated as terminal by the reaper
"""

from __future__ import annotations

import inspect

from app.services.review_pipeline import orchestrator


def test_no_reject_branch_uses_status_reviewing():
    """Source check: pre-PR-75 every reject path set status='reviewing'.
    PR #75: none should. The startup line that sets 'reviewing' on
    pipeline entry is fine (correct semantics during work)."""
    src = inspect.getsource(orchestrator.run_review_pipeline)
    # Count only NON-comment lines using status="reviewing".
    code_uses = sum(
        1
        for line in src.splitlines()
        if 'status="reviewing"' in line and not line.strip().startswith("#")
    )
    assert code_uses <= 1, (
        f"Expected at most 1 code line with status=reviewing (the "
        f"pipeline-entry one); got {code_uses}. Reject branches must "
        f"use status='rejected'."
    )


def test_l1_fail_branch_sets_rejected():
    """L1 structural fail → terminal rejected."""
    src = inspect.getsource(orchestrator.run_review_pipeline)
    # The L1 fail block contains both 'L1 FAILED' and 'rejected'.
    l1_pos = src.find("L1 FAILED")
    assert l1_pos > 0
    window = src[l1_pos : l1_pos + 1500]
    assert 'status="rejected"' in window, "L1 fail must set status=rejected"


def test_l2_fail_branch_sets_rejected():
    src = inspect.getsource(orchestrator.run_review_pipeline)
    l2_pos = src.find("L2 FAILED")
    assert l2_pos > 0
    window = src[l2_pos : l2_pos + 1500]
    assert 'status="rejected"' in window, "L2 fail must set status=rejected"


def test_both_l3_l4_fail_branch_sets_rejected():
    src = inspect.getsource(orchestrator.run_review_pipeline)
    pos = src.find("Both L3 and L4 reject")
    assert pos > 0
    window = src[pos : pos + 1500]
    assert 'status="rejected"' in window, "Both-fail branch must set status=rejected"


def test_decision_reject_branch_sets_rejected():
    """The final decision branch (computed_final_decision returned
    'reject') must also set rejected, not 'reviewing'."""
    src = inspect.getsource(orchestrator.run_review_pipeline)
    pos = src.find('elif decision == "reject"')
    assert pos > 0
    window = src[pos : pos + 800]
    assert 'status="rejected"' in window
    # No code line in this branch (excluding comments) should use
    # status="reviewing".
    code_uses = sum(
        1
        for line in window.splitlines()
        if 'status="reviewing"' in line and not line.strip().startswith("#")
    )
    assert code_uses == 0, "decision==reject branch must not use status=reviewing in code"


def test_escalate_branch_now_calls_set_paper_status():
    """Pre-PR-75 the escalate branch returned without calling
    _set_paper_status, leaving the paper at status='reviewing'.
    PR #75: it must call _set_paper_status with terminal values."""
    src = inspect.getsource(orchestrator.run_review_pipeline)
    pos = src.find("Escalation triggered")
    assert pos > 0
    window = src[pos : pos + 2000]
    # The escalate branch must call _set_paper_status before returning.
    assert "_set_paper_status" in window, (
        "Escalate branch must call _set_paper_status to flip status to "
        "terminal. Without this the paper stays at status='reviewing' "
        "and the orphan reaper kills it ~30 min later."
    )
    assert 'status="rejected"' in window
    # The review_status preserves the human-review signal.
    assert 'review_status="escalated"' in window or "escalated" in window


def test_pass_branch_unchanged_sets_candidate():
    """Regression guard: pass branch was already correct (status=
    'candidate' is terminal). PR #75 must not break it."""
    src = inspect.getsource(orchestrator.run_review_pipeline)
    pos = src.find('decision == "pass"')
    assert pos > 0
    window = src[pos : pos + 500]
    assert 'status="candidate"' in window


def test_revision_branch_unchanged():
    """Regression guard: revision_needed → status=revision.
    'revision' is currently NOT in the orphan reaper's terminal list
    but the cron's revision-handling step should pick it up. Don't
    change it as part of this PR — focus on the reject paths."""
    src = inspect.getsource(orchestrator.run_review_pipeline)
    pos = src.find('decision == "revision_needed"')
    assert pos > 0
    window = src[pos : pos + 500]
    assert 'status="revision"' in window


def test_references_production_paper():
    """Trace future-self to the paper that motivated this fix."""
    src = inspect.getsource(orchestrator.run_review_pipeline)
    assert "apep_427ca0f1" in src


def test_reaper_treats_rejected_as_terminal():
    """Source check on papers.py: 'rejected' must be in terminal_statuses
    so the reaper leaves rejected papers alone."""
    from app.api import papers

    src = inspect.getsource(papers.reap_orphan_papers)
    assert '"rejected"' in src or "'rejected'" in src
    # Find the terminal_statuses tuple specifically.
    pos = src.find("terminal_statuses")
    assert pos > 0


def test_module_imports_clean():
    assert orchestrator.run_review_pipeline is not None
