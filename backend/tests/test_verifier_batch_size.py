"""Tests that the Verifier's batch size keeps the LLM honest about
completeness.

Production data shows the LLM has a "comfortable response size" of
roughly N entries regardless of how many claims the prompt sends:

  batch_size=15 → ~11 entries returned (apep_80c3df8f, run 25187417178)
  batch_size=5  → ~1-3 entries returned (apep_8f5c16b6, run 25190341746)

Smaller batches DIDN'T fix the partial-response problem — the LLM
just cherry-picks within whatever batch size you give it. The
structural fix is batch_size=1: when the LLM has exactly one claim
to verify per call, it has nothing to drop.

This file's tests prevent a future revert above 1 (which has been
shown empirically to leak claims to ``pending`` status).
"""

from __future__ import annotations

from app.services.paper_generation.roles import verifier as verifier_mod


def test_verifier_batch_size_is_one():
    """PR #53 sets the batch size to 1 — per-claim verification.

    Earlier sizes left claims stuck at "pending" status:
      - 50: truncated, 0 statuses returned (apep_28011bda)
      - 15: 11/25 statuses, 14 pending (apep_80c3df8f)
      - 5:  6/18 statuses, 12 pending (apep_8f5c16b6)

    With 1, the LLM has a single task per call and can't drop work.
    """
    assert verifier_mod._VERIFIER_BATCH_SIZE == 1, (
        f"_VERIFIER_BATCH_SIZE={verifier_mod._VERIFIER_BATCH_SIZE} should "
        f"be 1. Sizes >1 saw the LLM cherry-pick which claims to verify "
        f"and leave the rest at 'pending' — see comment block in "
        f"verifier.py for the production size→coverage data."
    )


def test_verifier_batch_size_is_at_least_1():
    """Defensive: 0 or negative would deadloop the per-batch range()."""
    assert verifier_mod._VERIFIER_BATCH_SIZE >= 1


def test_25_claims_fits_in_25_calls():
    """Drafter caps at _MAX_CLAIMS_PER_PAPER = 25 (PR #36). With
    batch=1 that's 25 LLM calls. Each call is small (~5-10s), so
    total Verifier wall-clock stays well under the 600s stage budget
    (PR #46)."""
    typical_claim_count = 25
    n_batches = (
        typical_claim_count + verifier_mod._VERIFIER_BATCH_SIZE - 1
    ) // verifier_mod._VERIFIER_BATCH_SIZE
    assert n_batches <= 25, (
        f"With batch size {verifier_mod._VERIFIER_BATCH_SIZE} and 25 "
        f"claims, expected <= 25 batches; got {n_batches}."
    )
