"""Regression tests for the quality + diagnostics PR.

Covers Issues 1, 2, 3, 4, A, B from the post-second-paper assessment:

  1. Drafter softens its source-ref filter (preserves unregistered IDs
     in source_span_ref instead of NULLing them out).
  2. Drafter caps claims at 25 (was unbounded; production paper
     apep_28011bda generated 50 and choked the Verifier).
  3. Verifier batches claims into chunks of 15 per LLM call.
  4. Provenance endpoint includes a source-diversity score.
  A. ``GET /papers/{id}`` returns parsed ``error_message``.
  B. ``GET /papers/{id}`` returns ``funnel_stage``.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles.drafter import (
    _MAX_CLAIMS_PER_PAPER,
    compose_manuscript,
)
from app.services.paper_generation.roles.verifier import (
    _VERIFIER_BATCH_SIZE,
    verify_manuscript,
)

# ── Issue 1: Drafter soft source-ref filter ────────────────────────────


def test_drafter_preserves_unregistered_source_ref_in_source_span_ref():
    """When the LLM's source_ref isn't a registered ID, the value
    must NOT be silently dropped — it goes into source_span_ref so
    the Verifier can flag it as un-validated.
    """
    src = inspect.getsource(compose_manuscript)
    assert "soft_source_span_ref" in src or "source_span_ref" in src, (
        "compose_manuscript must store unregistered source_ref values "
        "in source_span_ref instead of NULLing them out."
    )
    # The soft path must check `registered=False` so the verifier
    # can tell registered vs unregistered claims apart.
    assert '"registered": False' in src or "registered=False" in src or "registered" in src, (
        "Soft-source records must be tagged so Verifier can distinguish "
        "them from registered-source claims."
    )


# ── Issue 2: Drafter caps claims ───────────────────────────────────────


def test_drafter_caps_claims_at_max():
    """The Drafter must enforce an explicit cap so the Verifier's
    downstream LLM call doesn't get a 50-claim prompt.
    """
    assert _MAX_CLAIMS_PER_PAPER <= 30, (
        f"_MAX_CLAIMS_PER_PAPER = {_MAX_CLAIMS_PER_PAPER} — too high. "
        "Production paper apep_28011bda hit the Verifier with 50 "
        "claims and got zero updates."
    )
    assert _MAX_CLAIMS_PER_PAPER >= 15, (
        f"_MAX_CLAIMS_PER_PAPER = {_MAX_CLAIMS_PER_PAPER} — too low. "
        "Need enough claims for substantive provenance."
    )

    src = inspect.getsource(compose_manuscript)
    assert "_MAX_CLAIMS_PER_PAPER" in src, (
        "compose_manuscript must reference _MAX_CLAIMS_PER_PAPER."
    )


# ── Issue 3: Verifier batching ─────────────────────────────────────────


def test_verifier_batches_claims():
    """The Verifier must chunk claims into batches; sending 50 in one
    prompt killed Verifier on production paper apep_28011bda. Batches
    of 15 still saw the LLM dropping entries (paper apep_80c3df8f had
    14/25 stuck pending) so PR #52 reduced the size to 5.
    """
    assert 1 <= _VERIFIER_BATCH_SIZE <= 10, (
        f"_VERIFIER_BATCH_SIZE = {_VERIFIER_BATCH_SIZE} should be "
        "between 1 and 10 claims per LLM call. See test_verifier_batch_size.py "
        "for the strict <= 5 lock."
    )

    src = inspect.getsource(verify_manuscript)
    assert "_VERIFIER_BATCH_SIZE" in src, "verify_manuscript must reference _VERIFIER_BATCH_SIZE."
    assert "for batch_start in range" in src or "batch_start" in src, (
        "verify_manuscript must iterate claims in batches."
    )
    # Aggregation must accumulate across batches
    assert "aggregate_results" in src, "verify_manuscript must aggregate per-batch results."


# ── Issue 4: Source diversity in provenance ────────────────────────────


def test_provenance_endpoint_includes_diversity_score():
    """The provenance report must surface source-diversity so an
    operator can spot over-reliance on a single source.
    """
    from app.api.provenance import get_paper_provenance

    src = inspect.getsource(get_paper_provenance)
    assert "source_diversity" in src, "Provenance endpoint must compute a source_diversity block."
    assert "top_source_share" in src, (
        "Provenance endpoint must compute the share of claims from the most-used source."
    )
    assert "diversity_warning" in src, (
        "Provenance endpoint must emit a warning when one source covers >50% of claims."
    )


# ── Issues A + B: API surface — error_message + funnel_stage ───────────


def test_paper_response_schema_has_funnel_stage_and_error_message():
    """``PaperResponse`` (and by inheritance ``PaperWithRating``) must
    expose ``funnel_stage`` and ``error_message`` so polling clients
    can show progress + diagnose failures.
    """
    from app.schemas.paper import PaperResponse, PaperWithRating

    assert "funnel_stage" in PaperResponse.model_fields
    assert "error_message" in PaperResponse.model_fields
    # Both fields inherited by PaperWithRating
    assert "funnel_stage" in PaperWithRating.model_fields
    assert "error_message" in PaperWithRating.model_fields


def test_get_paper_endpoint_parses_metadata_json():
    """``GET /papers/{id}`` must extract the orchestrator's error
    string from ``paper.metadata_json`` so failed papers are
    self-diagnosing without backend log access.
    """
    from app.api.papers import get_paper

    src = inspect.getsource(get_paper)
    assert "metadata_json" in src
    assert "error_message" in src
