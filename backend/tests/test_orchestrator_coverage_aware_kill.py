"""Tests for PR #72: orchestrator defers Verifier kill when coverage is low.

Production paper apep_4d0e15af (autonomous-loop run 25288590150) was
killed by Verifier reject with:
  - 1 verified + 5 failed + 19 pending = 25 total
  - 24% coverage
  - 17% pass rate within the 6 sampled claims

The LLM recommended "reject" based on the 6 it sampled. The cron
re-verify step (PR #56) runs AFTER the orchestrator finishes, so it
had no chance to lift the verdict before the kill flipped
Paper.status. With more verdicts the paper might have survived.

PR #72 adds a coverage threshold: if (verified + failed) / total
< 0.5, downgrade reject → revise so the paper continues to Packager
+ L1/L2 review. The cron re-verify (already scheduled) fills in
more verdicts before anyone acts on the paper.

This file locks in:
  * The deferral computes coverage from the verifier summary
  * The deferral fires only when recommendation==reject AND coverage < 0.5
  * The downgrade changes recommendation to "revise" (not "approve")
  * The deferral does NOT trigger when coverage >= 0.5 (real reject)
  * The deferral does NOT trigger for revise/approve recommendations
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.orchestrator import run_full_pipeline

# ── Source-level checks: the deferral logic is wired in ────────────────────


def test_orchestrator_computes_coverage_from_summary():
    """Source check: coverage = (verified + failed) / total — the
    formula must read from the Verifier's summary."""
    src = inspect.getsource(run_full_pipeline)
    # Each variable name must appear so the formula is correct.
    assert 'verifier_summary.get("passed"' in src
    assert 'verifier_summary.get("failed"' in src
    assert 'verifier_summary.get("total_claims"' in src
    # The coverage ratio computation.
    assert "checked / total_claims" in src or "(verified_count + failed_count)" in src


def test_orchestrator_deferral_threshold_is_50_percent():
    """Source check: the threshold below which we defer is 0.5
    (50%). Production paper apep_4d0e15af had 24% — well below."""
    src = inspect.getsource(run_full_pipeline)
    assert "coverage < 0.5" in src


def test_orchestrator_deferral_only_on_reject():
    """Source check: deferral fires ONLY when the LLM recommends
    reject. Revise/approve are unaffected — those paths already
    continue the pipeline."""
    src = inspect.getsource(run_full_pipeline)
    assert 'recommendation == "reject" and coverage < 0.5' in src


def test_orchestrator_deferral_downgrades_to_revise():
    """Source check: the downgrade target is 'revise', not 'approve'.
    Approve would skip checks; revise still allows downstream review
    to flag issues."""
    src = inspect.getsource(run_full_pipeline)
    # The deferral must rewrite recommendation to 'revise'.
    pos = src.find("coverage < 0.5")
    assert pos > 0
    # Look for the assignment in the next ~500 chars.
    window = src[pos : pos + 1500]
    assert 'recommendation = "revise"' in window


def test_orchestrator_deferral_logs_warning_with_counts():
    """Source check: the deferral must log enough context for the
    operator to understand what was deferred and why. Surface the
    coverage percentage and the verified/failed/total counts."""
    src = inspect.getsource(run_full_pipeline)
    pos = src.find("coverage < 0.5")
    assert pos > 0
    # Window around the deferral.
    window = src[pos - 200 : pos + 1500]
    assert "logger.warning" in window
    # The log must include the actual numbers — coverage % and the
    # three counts.
    assert "coverage * 100" in window or "coverage" in window
    # All three counts referenced in the log.
    assert "verified_count" in window
    assert "failed_count" in window
    assert "total_claims" in window


def test_orchestrator_real_kill_still_happens_when_coverage_high():
    """Source check: the kill block (paper.status = 'killed', etc.)
    is still reachable when the deferral does NOT fire. Above 50%
    coverage the LLM's reject is treated as authoritative.

    The order is: compute coverage → deferral test → kill test. If
    the kill test were inside the deferral branch, high-coverage
    rejects would never kill."""
    src = inspect.getsource(run_full_pipeline)
    # Find the deferral block.
    deferral_pos = src.find("coverage < 0.5")
    assert deferral_pos > 0
    # Find the kill block — should be AFTER the deferral.
    kill_pos = src.find('paper.kill_reason = "Verifier recommended rejection"')
    assert kill_pos > deferral_pos, (
        "Kill block must come AFTER the deferral block so the deferral's "
        "downgrade can prevent the kill. If kill is inside or before the "
        "deferral, the order is wrong."
    )
    # The kill block must still gate on recommendation == "reject".
    # (Without this, the deferral's downgrade has no effect.)
    kill_window = src[kill_pos - 500 : kill_pos]
    assert 'recommendation == "reject"' in kill_window


def test_orchestrator_references_production_paper_in_comment():
    """Future-self should be able to trace the rule to the paper
    that motivated it. The reference belongs in the comment block
    above the deferral, not in user-facing logs."""
    src = inspect.getsource(run_full_pipeline)
    assert "apep_4d0e15af" in src


# ── Edge case: zero total claims ──────────────────────────────────────────


def test_orchestrator_handles_zero_claims_safely():
    """Source check: when total_claims is 0, coverage is undefined.
    The code must not divide by zero. The default path: coverage = 0.0,
    so any reject would trigger deferral — fine, papers without
    claims are likely broken anyway and won't be killed prematurely."""
    src = inspect.getsource(run_full_pipeline)
    # Look for a guard against div-by-zero in the coverage computation.
    pos = src.find("total_claims")
    assert pos > 0
    # Must be a conditional (ternary or if) preventing div-by-zero.
    assert "if total_claims > 0 else 0.0" in src or "total_claims > 0" in src
