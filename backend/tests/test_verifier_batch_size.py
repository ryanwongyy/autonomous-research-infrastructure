"""Tests that the Verifier's batch size is small enough to keep the
LLM honest about completeness.

Production paper apep_80c3df8f (autonomous-loop run 25187417178)
reached the Verifier with 25 claims, batched as 15 + 10. The LLM
returned only 11 verifications in batch 0 (skipping the first 4
claims) and 0 verifications in batch 1 — leaving 14 of 25 claims
stuck at ``pending`` even though PR #50 had added explicit
\"verify EVERY claim\" instructions to the prompt.

Smaller batches make the LLM's task small enough that it can't
plausibly drop entries. PR #52 reduces the batch size to 5; this
test prevents a future revert that would bring the production
failure mode back.
"""

from __future__ import annotations

from app.services.paper_generation.roles import verifier as verifier_mod


def test_verifier_batch_size_is_small():
    """Batch size <= 5 so the LLM can't drop entries even on a
    \"lazy\" response. Bigger batches saw 4-/15 and 0-/10 dropouts in
    production (paper apep_80c3df8f)."""
    assert verifier_mod._VERIFIER_BATCH_SIZE <= 5, (
        f"_VERIFIER_BATCH_SIZE={verifier_mod._VERIFIER_BATCH_SIZE} is too "
        f"large; production runs at 15 dropped 14/25 claims to pending. "
        f"Keep at <= 5."
    )


def test_verifier_batch_size_is_at_least_1():
    """Defensive: 1 is fine (per-claim verification, expensive but
    bulletproof). 0 or negative would deadloop or silently skip work."""
    assert verifier_mod._VERIFIER_BATCH_SIZE >= 1


def test_25_claims_now_fit_in_at_most_5_batches():
    """A typical production paper (drafter cap _MAX_CLAIMS_PER_PAPER = 25
    per PR #36) generates 25 claims. With batch size 5, that's exactly
    5 LLM calls — bounded and predictable."""
    typical_claim_count = 25
    n_batches = (
        typical_claim_count + verifier_mod._VERIFIER_BATCH_SIZE - 1
    ) // verifier_mod._VERIFIER_BATCH_SIZE
    assert n_batches <= 5, (
        f"With batch size {verifier_mod._VERIFIER_BATCH_SIZE} and 25 "
        f"claims, expected at most 5 batches; got {n_batches}."
    )
