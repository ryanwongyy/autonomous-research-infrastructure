"""Tests for PR #73: L2 ``coverage_incomplete`` is no longer CRITICAL.

Production paper apep_82532feb (autonomous-loop run 25289671965)
exposed an inconsistency between PR #54's design intent and L2's
threshold:

PR #54 redefined coverage_ratio as (verified + failed) / total — i.e.
Verifier process completeness, NOT verification pass rate. CLAUDE.md
documents the intent: "Quality issues surface via the failed count
and tier_violations, not via degraded coverage."

But L2's coverage_incomplete check still fired CRITICAL when coverage
< 0.8 — and the LLM's documented cherry-picking behavior (~30-50%
verdict rate per batch) means no first-pass paper can reach 80%.
Every paper got a CRITICAL coverage_incomplete on its first L2 review.

PR #73 downgrades the check to severity=warning at all coverage levels.
The redundant `verification_pending` warning already surfaces the
pending count for operator awareness. Real quality issues
(`verification_failures`, `tier_violations`, `unresolved_data_object`,
fabricated citations) remain CRITICAL.

This file locks in:
  * coverage_incomplete uses severity=warning, NOT critical
  * The check still fires when coverage < 1.0 (operator sees it)
  * The message no longer says "Full coverage required"
  * The numerator in the message is verified+failed, not just verified
  * Real quality checks remain critical (regression guard)
"""

from __future__ import annotations

import inspect

from app.services.review_pipeline import l2_provenance


def test_coverage_incomplete_is_no_longer_critical():
    """The severity bifurcation at 0.8 (warning vs critical) is gone.
    coverage_incomplete fires only at warning."""
    src = inspect.getsource(l2_provenance)
    # The old expression must be gone.
    assert '"warning" if coverage >= 0.8 else "critical"' not in src
    # The check must still appear, with severity warning.
    pos = src.find('"check": "coverage_incomplete"')
    assert pos > 0, "coverage_incomplete check must still exist"
    window = src[pos : pos + 400]
    assert '"severity": "warning"' in window, (
        "coverage_incomplete must be severity=warning at all coverage levels"
    )


def test_coverage_message_no_longer_demands_full_coverage():
    """The old message said 'Full coverage required'. Per PR #54's
    design intent, full coverage is NOT required — re-verify fills
    in pending claims over multiple cron ticks."""
    src = inspect.getsource(l2_provenance)
    assert "Full coverage required" not in src, (
        "L2 must not claim 'Full coverage required'. PR #54's coverage "
        "metric measures Verifier process completeness, not a pass/fail "
        "gate."
    )


def test_coverage_message_uses_verified_plus_failed_numerator():
    """The displayed coverage uses (verified + failed) / total, matching
    PR #54's formula. The old message used just verified/total which
    misled operators into thinking failures didn't count toward coverage."""
    src = inspect.getsource(l2_provenance)
    pos = src.find('"check": "coverage_incomplete"')
    assert pos > 0
    window = src[pos : pos + 800]
    # The message should reference verified+failed in the numerator.
    assert (
        "verified'] + claim_report['failed']" in window or "verified + failed" in window
    )


def test_coverage_message_mentions_re_verify():
    """The replacement message should tell operators that pending
    claims will be filled in by cron re-verify (PR #56) — otherwise
    they'll worry about a benign warning."""
    src = inspect.getsource(l2_provenance)
    pos = src.find('"check": "coverage_incomplete"')
    assert pos > 0
    window = src[pos : pos + 800]
    assert "re-verify" in window.lower(), (
        "Coverage warning should mention cron re-verify so operators "
        "understand pending claims will eventually be filled in."
    )


def test_real_quality_checks_remain_critical():
    """Regression guard: PR #73 must NOT downgrade real quality
    signals. verification_failures and tier_violations were CRITICAL
    before and must remain CRITICAL after."""
    src = inspect.getsource(l2_provenance)
    # verification_failures must still be critical when failures > 0.
    fail_pos = src.find('"check": "verification_failures"')
    assert fail_pos > 0
    fail_window = src[fail_pos : fail_pos + 300]
    assert '"severity": "critical"' in fail_window, (
        "verification_failures must remain severity=critical — that's "
        "a real quality signal, not Verifier completeness."
    )

    # tier_violations also critical.
    tier_pos = src.find("tier_violation")
    assert tier_pos > 0


def test_references_production_paper_in_comment():
    """Future-self trace to the paper that motivated the fix."""
    src = inspect.getsource(l2_provenance)
    assert "apep_82532feb" in src


def test_l2_module_imports_clean():
    """Sanity check: the file still parses and the function is
    callable."""
    assert l2_provenance.run_provenance_review is not None
