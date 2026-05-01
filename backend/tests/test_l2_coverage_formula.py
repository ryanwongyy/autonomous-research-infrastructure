"""Tests that L2's claim-verification coverage measures Verifier
completeness, not pass rate.

Pre-PR #54: ``coverage_ratio = verified / total_claims``. A paper
where Verifier processed all 25 claims and 12 failed (a real
quality signal) was indistinguishable from one where Verifier
only reached 13 of 25 (a Verifier completeness issue). Both got
CRITICAL ``coverage_incomplete`` from L2.

PR #54: ``coverage_ratio = (verified + failed) / total``. Now
``coverage_incomplete`` fires only when Verifier failed to process
claims, not when it processed them and found problems. Quality
issues surface separately via ``failed`` count + ``tier_violations``.

This test inspects the formula at the source level (the function
opens its own DB session via async_session, so a unit test against
the formula is the cleanest contract).
"""

from __future__ import annotations

import inspect

from app.services.provenance.claim_verifier import verify_paper_claims


def test_coverage_ratio_uses_verified_plus_failed():
    """Source check: the new formula counts both verified and failed
    in the numerator — the only way to distinguish 'didn't reach' from
    'reached but failed'."""
    src = inspect.getsource(verify_paper_claims)
    # Old formula was `verified / total_claims` — must be gone.
    assert "verified / total_claims" not in src, (
        "Old coverage formula (verified-only) must not appear; PR #54 "
        "changed to processed/total."
    )
    # New formula must add verified + failed (in that order or
    # symmetric).
    assert (
        "verified + failed" in src
        or "failed + verified" in src
        or "processed = verified + failed" in src
    ), "New formula must sum verified + failed for the coverage numerator."


def test_pass_rate_is_separately_reported():
    """The pass-rate dimension (verified / processed) should be
    available as a distinct metric so quality reporting can use it."""
    src = inspect.getsource(verify_paper_claims)
    assert "pass_rate" in src, (
        "verify_paper_claims should compute pass_rate as a separate "
        "field so callers can distinguish coverage from quality."
    )


def test_zero_processed_does_not_crash_pass_rate():
    """When Verifier reached zero claims (verified=failed=0), the
    pass_rate calc must not divide by zero."""
    src = inspect.getsource(verify_paper_claims)
    # Look for a defensive 'if processed > 0' or similar guard.
    assert (
        "if processed > 0" in src
        or ("if total_claims > 0" in src and "pass_rate = verified / processed" not in src)
        or "processed > 0 else 0" in src
    ), "pass_rate must guard against zero division."


def test_return_dict_includes_pass_rate():
    """The function's return dict must carry pass_rate so downstream
    code (L2 review, dashboards) can present quality alongside
    coverage."""
    src = inspect.getsource(verify_paper_claims)
    # The return dict should mention pass_rate as a key.
    assert '"pass_rate"' in src, (
        "Return dict must include pass_rate so L2 / dashboards can read it."
    )


def test_verified_failed_pending_still_in_return():
    """Pre-existing fields shouldn't be dropped by the formula change."""
    src = inspect.getsource(verify_paper_claims)
    for field in ('"verified"', '"failed"', '"pending"', '"coverage_ratio"'):
        assert field in src, f"Return dict must preserve {field}."
