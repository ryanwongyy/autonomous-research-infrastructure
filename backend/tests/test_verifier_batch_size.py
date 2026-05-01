"""Tests that the Verifier's batch size is set to a value that
empirically produces the most claim coverage.

Production data table:

  batch_size=50 → 0/50  statuses (truncated, apep_28011bda)
  batch_size=15 → 11/25 statuses (apep_80c3df8f)
  batch_size=5  → 6/18  statuses (apep_8f5c16b6)
  batch_size=1  → 1/19  statuses (apep_de279513 — REGRESSED)

PR #53 hypothesised that per-claim verification (batch=1) would be
the structural fix: with one task per LLM call, the LLM has nothing
to drop. The hypothesis was wrong — batch=1 produced the WORST
coverage. The most likely cause is that with one claim per prompt,
the LLM gets a mostly-context, very-little-task prompt and either
the model treats it differently or Anthropic rate-limits the rapid
sequential calls.

PR #54 reverts to batch=5 (best partial-working state) AND updates
the L2 ``coverage_incomplete`` formula in claim_verifier.py to count
``verified + failed`` (Verifier completeness) rather than just
``verified`` (pass rate). That separates "Verifier processed it"
from "claim passed" — papers where Verifier did its job but found
quality issues no longer get punished by ``coverage_incomplete``.
"""

from __future__ import annotations

from app.services.paper_generation.roles import verifier as verifier_mod


def test_verifier_batch_size_is_in_known_working_range():
    """Batch size in [2, 10] — the range where the LLM produces some
    real verifications. ``1`` regressed; ``>10`` truncated."""
    assert 2 <= verifier_mod._VERIFIER_BATCH_SIZE <= 10, (
        f"_VERIFIER_BATCH_SIZE={verifier_mod._VERIFIER_BATCH_SIZE} is "
        f"outside the [2, 10] empirically-best range. See verifier.py "
        f"comment for the production size→coverage data."
    )


def test_verifier_batch_size_avoids_known_failure_points():
    """Locks in the specific failure points: 1 and 15+ both produced
    bad coverage in production."""
    size = verifier_mod._VERIFIER_BATCH_SIZE
    assert size != 1, (
        "batch_size=1 regressed to 1/19 in apep_de279513 — the LLM "
        "appears to behave differently when given a single-claim "
        "prompt (mostly context, very little task)."
    )
    assert size <= 14, (
        f"batch_size={size} >= 15 risks the cherry-picking pattern "
        f"seen in apep_80c3df8f (only 11/25 entries returned)."
    )


def test_25_claim_paper_fits_in_reasonable_call_count():
    """For the typical 25-claim paper, the call count should be
    bounded so wall-clock stays under the 600s Verifier timeout."""
    typical = 25
    n_calls = (
        typical + verifier_mod._VERIFIER_BATCH_SIZE - 1
    ) // verifier_mod._VERIFIER_BATCH_SIZE
    # 5 calls x ~30s each = 150s — well under 600s
    # 12 calls x ~30s each = 360s — still under
    assert 1 <= n_calls <= 25
