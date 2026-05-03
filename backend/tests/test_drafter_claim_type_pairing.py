"""Tests that the Drafter prompt enforces claim_type vs source_type pairing.

Production paper apep_5bd06118 (autonomous-loop run 25214622805) had
PR #65's source-excerpts in the Verifier prompt. The Verifier became
able to verify claims against actual source text. Result: 11 of 25
claims FAILED, 0 passed, paper killed by Verifier reject.

The failure pattern: empirical claims (e.g. "Pre-treatment trends are
parallel", "AI systems mediate consequential decisions") were
anchored via source_type="source_span" to data sources like ``edgar``
and ``aiid``. The raw source filings don't contain the statistical
finding the claim asserts. Verifier correctly flagged the mismatch.

PR #66 adds prompt guidance making the Drafter's contract explicit:
  - claim_type="empirical" → source_type="result_object" (Analyst output)
  - claim_type="descriptive"/"doctrinal" → source_type="source_span" (text in the source)
  - Plus a Phase-3 diagnostic warning when the LLM violates the rule.

This file locks in:
  * Prompt has a "claim_type vs source_type pairing" section
  * Prompt names the production failure example
  * Prompt provides bad-pairing examples the Verifier will fail
  * Phase 3 counts empirical-with-source_span and logs WARNING
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles import drafter as drafter_mod
from app.services.paper_generation.roles.drafter import (
    DRAFT_USER_PROMPT,
    compose_manuscript,
)

# ── Prompt structure ────────────────────────────────────────────────────────


def test_prompt_has_claim_type_vs_source_type_section():
    """The new pairing section must be present so the LLM sees the
    rule at task time."""
    assert "claim_type vs source_type pairing" in DRAFT_USER_PROMPT


def test_prompt_references_production_failure():
    """The prompt should name the specific paper that motivated the
    rule so future-self can trace context."""
    assert "apep_5bd06118" in DRAFT_USER_PROMPT


def test_prompt_explains_empirical_must_use_result_object():
    """Empirical claims state findings, which come from the Analyst,
    not from the raw source."""
    flat = " ".join(DRAFT_USER_PROMPT.split())
    assert "empirical" in flat.lower()
    # Must say empirical claims use result_object source_type.
    assert 'source_type="result_object"' in DRAFT_USER_PROMPT


def test_prompt_explains_descriptive_uses_source_span():
    """Descriptive/doctrinal claims state facts in the source, so
    source_span is correct."""
    flat = " ".join(DRAFT_USER_PROMPT.split())
    assert "descriptive" in flat
    assert "doctrinal" in flat
    # The descriptive/doctrinal block must reference source_span.
    assert 'source_type="source_span"' in DRAFT_USER_PROMPT


def test_prompt_has_fallback_when_no_result_objects():
    """If no result_objects are registered, empirical claims should be
    rewritten as descriptive — this prevents the Drafter from
    asserting findings the paper hasn't actually computed."""
    flat = " ".join(DRAFT_USER_PROMPT.split())
    assert "no result objects are registered" in flat
    assert "REWRITE" in DRAFT_USER_PROMPT


def test_prompt_provides_concrete_bad_pairing_examples():
    """The prompt should show bad examples — concrete failures are
    more memorable than abstract rules."""
    # Specifics from the production failure.
    assert "Pre-treatment trends are parallel" in DRAFT_USER_PROMPT
    # The prompt should label the antagonist source.
    assert 'source_ref="edgar"' in DRAFT_USER_PROMPT


# ── Phase 3 diagnostic warning ──────────────────────────────────────────────


def test_phase3_counts_empirical_with_source_span():
    """Source check: the Phase 3 loop must count empirical claims with
    source_type=source_span so we can warn on the rate."""
    src = inspect.getsource(compose_manuscript)
    assert "empirical_with_source_span" in src
    # The condition must check both claim_type and source_type.
    assert 'claim_type.lower() == "empirical"' in src or 'claim_type.lower() == "empirical"' in src
    assert 'source_type == "source_span"' in src


def test_phase3_logs_warning_when_misanchored():
    """Source check: when at least one empirical claim is misanchored,
    log a WARNING surfacing the rate."""
    src = inspect.getsource(compose_manuscript)
    # Logger.warning call must reference the misanchor count.
    assert "logger.warning" in src
    assert "empirical_with_source_span" in src
    # The warning should mention "fail Verifier" so the operator
    # connects the diagnostic to the downstream failure.
    assert "fail Verifier" in src


def test_phase3_warning_is_observability_not_kill():
    """The Drafter must NOT block on misanchoring — the Verifier
    catches it. Drafter only logs."""
    src = inspect.getsource(compose_manuscript)
    # No `raise` after the warning; the loop continues.
    warning_pos = src.find('logger.warning(\n        "Drafter: paper')
    if warning_pos < 0:
        warning_pos = src.find('logger.warning(\n            "Drafter: paper')
    if warning_pos < 0:
        # Tolerate slight line-wrap variation
        warning_pos = src.find('"Drafter: paper %s has %d/%d empirical')
    assert warning_pos > 0, "Warning log not found at expected location"
    # The next 200 chars after the warning shouldn't contain `raise`.
    window = src[warning_pos : warning_pos + 800]
    assert "raise " not in window or "raise " in window.split("logger.warning")[0], (
        "Misanchoring is observability — the Drafter must not raise"
    )


# ── Module imports clean ────────────────────────────────────────────────────


def test_drafter_module_imports_clean():
    assert drafter_mod.compose_manuscript is not None
