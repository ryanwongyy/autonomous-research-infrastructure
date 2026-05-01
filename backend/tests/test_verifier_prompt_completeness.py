"""Tests that the Verifier prompt and post-LLM check enforce
completeness — every claim sent to the LLM should come back with a
verification entry.

Production paper apep_3cdecd97 (autonomous-loop run 25185772689) sent
25 claims to the Verifier in 2 batches (15 + 10). The LLM returned
only 5 / 6 claims per batch — leaving 14 of 25 stuck at
verification_status='pending' even though PR #47's id-matching
worked correctly. The bug was in the **prompt**, not the matcher:
the LLM was cherry-picking which claims to verify because nothing
in the prompt explicitly required completeness.

This file locks in:

  * The prompt template includes ``{claim_count}`` so the LLM sees
    the exact target count.
  * The prompt has an explicit \"CRITICAL COMPLETENESS REQUIREMENT\"
    section instructing the LLM to output exactly N entries, in
    order, with claim_id matching.
  * ``verify_manuscript`` formats the prompt with ``claim_count``.
  * A post-LLM check warns when the response falls short of the
    batch size (observability for prompt failures).
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles import verifier as verifier_mod
from app.services.paper_generation.roles.verifier import (
    VERIFY_USER_PROMPT,
    verify_manuscript,
)


# ── Prompt template content ──────────────────────────────────────────────────


def test_prompt_template_has_claim_count_placeholder():
    """The template uses ``{claim_count}`` so each batch's call passes
    its exact size."""
    # f-string-style placeholder. The whole template is fed through
    # str.format(), so single-brace {claim_count} is a substitution
    # while double-brace {{ }} are JSON literals.
    assert "{claim_count}" in VERIFY_USER_PROMPT


def test_prompt_has_explicit_completeness_section():
    """The prompt must contain a strongly-worded completeness
    requirement so the LLM doesn't cherry-pick claims."""
    assert "CRITICAL COMPLETENESS REQUIREMENT" in VERIFY_USER_PROMPT
    # Must instruct exactly N entries
    assert "EXACTLY {claim_count}" in VERIFY_USER_PROMPT
    # Must instruct same order
    assert "SAME ORDER" in VERIFY_USER_PROMPT
    # Must explicitly forbid skipping
    assert "Do NOT skip claims" in VERIFY_USER_PROMPT


def test_prompt_provides_uncertain_fallback():
    """Tell the LLM what to do with claims it can't verify with
    confidence — output 'warning' rather than dropping the entry."""
    assert "warning" in VERIFY_USER_PROMPT
    # Must explicitly say "still output an entry" so the LLM doesn't
    # treat uncertainty as a reason to skip.
    assert "still output an entry" in VERIFY_USER_PROMPT


# ── verify_manuscript wires the count through ────────────────────────────────


def test_verify_manuscript_passes_claim_count_to_format():
    """Source inspection: the call to ``VERIFY_USER_PROMPT.format(...)``
    inside ``verify_manuscript`` must pass ``claim_count=len(batch)``."""
    src = inspect.getsource(verify_manuscript)
    assert "claim_count=len(batch)" in src, (
        "verify_manuscript must pass claim_count=len(batch) so the "
        "prompt's CRITICAL COMPLETENESS REQUIREMENT references the "
        "actual target number."
    )


# ── Post-LLM completeness check ──────────────────────────────────────────────


def test_short_llm_response_logs_warning():
    """Source inspection: the per-batch loop must compare
    ``len(batch_results)`` to ``len(batch)`` and log a WARNING when
    the LLM came back short. This is observability — the operator
    needs a signal when prompt completeness fails."""
    src = inspect.getsource(verify_manuscript)
    assert "len(batch_results) < len(batch)" in src, (
        "verify_manuscript must check whether the LLM's response is "
        "short of the batch size and log a warning."
    )
    # The warning text should mention the gap so it's actionable.
    assert "logger.warning" in src
    # Mention pending so reading the log makes the consequence clear
    assert "pending" in src


def test_completeness_check_does_not_drop_partial_results():
    """Even when the LLM returns fewer entries than expected, the
    aggregator still extends with whatever did come back — partial
    progress is better than nothing. (Regression guard: ensure the
    completeness check is *observability*, not a hard gate.)"""
    src = inspect.getsource(verify_manuscript)
    # `aggregate_results.extend(batch_results)` must still run after
    # the warning check.
    extend_pos = src.find("aggregate_results.extend(batch_results)")
    warn_pos = src.find("len(batch_results) < len(batch)")
    assert extend_pos > 0
    assert warn_pos > 0
    # The extend must come AFTER the warning check.
    assert extend_pos > warn_pos, (
        "Partial-result fallback must run regardless of completeness "
        "check (the warning is for observability, not a hard kill)."
    )


# ── Module-level reference test (smoke) ──────────────────────────────────────


def test_module_imports_clean():
    """Sanity: the module loads without errors after the prompt edit."""
    assert verifier_mod.verify_manuscript is not None
    assert verifier_mod.VERIFY_USER_PROMPT is not None
