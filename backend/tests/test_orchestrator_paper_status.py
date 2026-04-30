"""Tests that the orchestrator flips Paper.status to a terminal value
on every pipeline outcome (success / verifier-rejected).

Production run #25163518619 generated a real paper end-to-end (Packager
ran, paper got funnel_stage=candidate, manuscript was written) but the
GitHub Actions cron timed out at 45 min because it polls Paper.status
which stayed at "draft" the whole time. The orchestrator was only
updating funnel_stage; this PR adds the missing status writes.

Terminal poll values (from the workflow's case statement in
.github/workflows/autonomous-loop.yml):
    candidate | published | error | killed | rejected

These tests use source inspection (matching the existing
test_long_running_pipeline.py pattern) so they don't depend on a
fully-mocked pipeline run — they assert the contract at the orchestrator's
two terminal-state code paths directly.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation import orchestrator


def test_success_path_sets_paper_status_to_candidate():
    """The success block — after Packager — must set paper.status =
    'candidate'. Without this, the cron poll loop never sees the paper
    leave 'draft' and times out at 45 min (production run #25163518619).
    """
    src = inspect.getsource(orchestrator.run_full_pipeline)

    # Find the pipeline-complete block: the final reload-paper after
    # Packager runs. Look for 'completed (funnel_stage=' as the marker.
    # The line preceding that string assignment must include
    # paper.status = "candidate".
    assert 'paper.status = "candidate"' in src, (
        'Orchestrator success path must set paper.status = "candidate". '
        "External observers (cron, frontend) poll Paper.status for "
        "terminal values; without this flip, generation looks identical "
        "to 'never started'."
    )

    # The status flip must be physically near the funnel_stage read so a
    # future refactor doesn't move them apart.
    success_marker = "completed (funnel_stage="
    pos = src.find(success_marker)
    assert pos >= 0, "expected success_marker in orchestrator source"
    # Look 500 chars before the marker for the status assignment.
    window = src[max(0, pos - 500) : pos]
    assert 'paper.status = "candidate"' in window, (
        "paper.status='candidate' assignment should immediately precede "
        "the success final_status string."
    )


def test_verifier_reject_path_sets_paper_status_to_killed():
    """When the verifier returns recommendation='reject', the orchestrator
    flips paper.funnel_stage='killed'. It must ALSO flip paper.status to
    'killed' so the cron poll loop's terminal-state check catches it.
    """
    src = inspect.getsource(orchestrator.run_full_pipeline)

    # Find the 'rejected_by_verifier' block.
    reject_marker = '"rejected_by_verifier"'
    pos = src.find(reject_marker)
    assert pos >= 0, "expected rejected_by_verifier marker in orchestrator source"

    # Look 800 chars BEFORE the marker for status='killed' assignment
    # (the marker is the LAST line of the block; the status flip is
    # earlier in the same block, right after funnel_stage='killed').
    window = src[max(0, pos - 800) : pos]
    assert 'paper.status = "killed"' in window, (
        "Verifier-rejection path must set paper.status='killed'. "
        "Without this, the cron polls forever — Paper.status stays at "
        "'draft' even though the paper is dead."
    )
    # And the funnel_stage flip should still be there too (regression
    # guard against accidentally replacing one with the other).
    assert 'paper.funnel_stage = "killed"' in window


def test_set_error_helper_writes_status_error():
    """The on-exception helper continues to write status='error' (this is
    pre-existing behaviour — locked in here so a refactor doesn't drop it).
    """
    src = inspect.getsource(orchestrator._set_error)
    assert 'status="error"' in src, (
        "_set_error must continue writing status='error' so cron sees the "
        "terminal state on uncaught pipeline exceptions."
    )
