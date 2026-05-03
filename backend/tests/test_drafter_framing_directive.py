"""Tests that the Drafter switches paper framing based on whether
the Analyst produced result objects.

Production paper apep_9afaf116 (autonomous-loop run 25217093244) had
PR #65's source excerpts and PR #66's claim-type/source-type pairing
rules in the Drafter prompt. The Analyst stage failed (unterminated
string literal in generated code) so result_manifest had no result
objects.

The Results section of the manuscript honestly admitted this: "We
note that due to a technical error in the analysis pipeline … the
quantitative analysis did not complete successfully." Good.

But the abstract still framed the paper as empirical:
  "we employ a difference-in-differences design to estimate the
   causal effect of audit clause inclusion on contractor compliance
   behavior"
And the conclusion repeated it. The Verifier (PR #65) caught the
claim-level mismatch but cannot catch a paper-level falsehood
because abstract/conclusion text has no claim_id.

PR #67 adds a FRAMING DIRECTIVE block to the prompt that switches
based on whether result_manifest contains result_objects. When
empty, it forbids "we find / we estimate / we show" framing and
requires the paper to be reframed as a research design or
measurement protocol.

This file locks in:
  * The prompt contains a {framing_directive} placeholder
  * _build_framing_directive returns the strict directive when
    no result_objects exist, and the permissive one when results
    are present
  * _count_empirical_framing_violations detects the forbidden
    framing phrases
  * Phase 3 logs WARNING when the manuscript uses forbidden phrases
    AND no result_objects were available
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles import drafter as drafter_mod
from app.services.paper_generation.roles.drafter import (
    DRAFT_USER_PROMPT,
    _build_framing_directive,
    _count_empirical_framing_violations,
    compose_manuscript,
)

# ── Prompt placeholder ──────────────────────────────────────────────────────


def test_prompt_has_framing_directive_placeholder():
    """Without the placeholder, format() raises on the new kwarg."""
    assert "{framing_directive}" in DRAFT_USER_PROMPT


def test_prompt_places_framing_directive_at_top():
    """The directive must appear before the lock_yaml so the LLM
    reads it first — paper-level framing rules are pre-emptive."""
    directive_pos = DRAFT_USER_PROMPT.index("{framing_directive}")
    lock_pos = DRAFT_USER_PROMPT.index("{lock_yaml}")
    assert directive_pos < lock_pos


# ── _build_framing_directive ────────────────────────────────────────────────


def test_directive_when_results_exist_is_permissive():
    """When the Analyst produced result objects, the paper may be
    framed as empirical — the directive should not forbid that."""
    text = _build_framing_directive(
        ["att_estimate", "parallel_trends_test"], "empirical_causal"
    )
    assert "analyst results available" in text.lower()
    # The count appears so the LLM sees the actual evidence base.
    assert "2" in text
    # No forbidden-phrases scaffolding here — that's only for the
    # no-results branch.
    assert "FORBIDDEN" not in text


def test_directive_when_no_results_forbids_we_find():
    """When result_objects is empty, the directive must explicitly
    forbid 'we find' framing — production paper apep_9afaf116
    used this exact phrasing in its abstract despite no analysis
    having run."""
    text = _build_framing_directive([], "empirical_causal")
    assert "NO ANALYST RESULTS" in text
    # Each forbidden phrase variant must be called out so the LLM
    # cannot satisfy the rule by switching synonyms.
    assert "We find" in text
    assert "We estimate" in text or "we estimate" in text
    assert "results show" in text.lower()
    assert "coefficient" in text.lower()


def test_directive_when_no_results_offers_reframings():
    """The directive must give the LLM a way out — concrete reframings
    so it doesn't simply lose the paper."""
    text = _build_framing_directive([], "empirical_causal")
    # Three viable reframings are required for different protocol shapes.
    assert "research design" in text.lower()
    assert (
        "measurement framework" in text.lower()
        or "measurement protocol" in text.lower()
    )
    assert "doctrinal analysis" in text.lower() or "interpretive" in text.lower()


def test_directive_references_production_failure():
    """Future-self should be able to trace the rule back to the paper
    that motivated it."""
    text = _build_framing_directive([], "empirical_causal")
    assert "apep_9afaf116" in text


def test_directive_carries_protocol_type_into_message():
    """The locked protocol_type is named so the LLM understands the
    tension: locked protocol says empirical, but no results exist."""
    text = _build_framing_directive([], "empirical_causal")
    assert "empirical_causal" in text


# ── _count_empirical_framing_violations ─────────────────────────────────────


def test_count_violations_zero_on_neutral_text():
    """Plain descriptive text has no forbidden phrases."""
    text = "This paper develops a research design for examining audit clauses."
    assert _count_empirical_framing_violations(text) == 0


def test_count_violations_detects_we_find():
    text = "We find that audit clauses increase compliance modifications."
    assert _count_empirical_framing_violations(text) >= 1


def test_count_violations_detects_we_estimate():
    text = "We estimate the causal effect of audit clause inclusion."
    assert _count_empirical_framing_violations(text) >= 1


def test_count_violations_detects_results_show():
    text = "Our results show a 23 percent increase in modifications."
    assert _count_empirical_framing_violations(text) >= 1


def test_count_violations_detects_apep_9afaf116_abstract():
    """Direct test against the production-failure abstract."""
    abstract = (
        "Exploiting staggered adoption of audit requirements across CFO Act "
        "agencies between 2023 and 2024, we employ a difference-in-differences "
        "design to estimate the causal effect of audit clause inclusion on "
        "contractor compliance behavior."
    )
    # 'we estimate' is the canonical hit here.
    assert _count_empirical_framing_violations(abstract) >= 1


def test_count_violations_case_insensitive():
    """Real LaTeX often has phrases mid-sentence with various casing."""
    upper = "WE FIND that audit clauses matter."
    assert _count_empirical_framing_violations(upper) >= 1


def test_count_violations_empty_input():
    """Empty manuscript returns 0, not an error."""
    assert _count_empirical_framing_violations("") == 0
    assert _count_empirical_framing_violations(None) == 0  # type: ignore[arg-type]


# ── Phase 3 diagnostic wires up ─────────────────────────────────────────────


def test_phase3_calls_violation_counter_when_no_results():
    """Source check: the Phase 3 path runs the framing scan only when
    ro_names is empty — when results exist the paper may legitimately
    say 'we find'."""
    src = inspect.getsource(compose_manuscript)
    assert "_count_empirical_framing_violations" in src
    # The condition gates on ro_names being empty.
    assert "not ro_names" in src


def test_phase3_logs_warning_with_violation_count():
    """Source check: warning surfaces the count so the operator can
    eyeball severity."""
    src = inspect.getsource(compose_manuscript)
    assert "logger.warning" in src
    assert "forbidden_framing_hits" in src
    # Mention the connection to the absent Analyst output.
    assert "no result_objects" in src


def test_phase3_warning_is_observability_not_kill():
    """The Drafter must not raise on a framing violation — the
    operator inspects and the next iteration tightens the prompt."""
    src = inspect.getsource(compose_manuscript)
    # The framing block must not raise. Check the window around the
    # warning call is free of `raise`.
    idx = src.find("forbidden_framing_hits")
    assert idx > 0
    window = src[idx : idx + 800]
    assert "raise " not in window


# ── compose_manuscript wires the directive into format() ───────────────────


def test_compose_manuscript_passes_framing_directive_to_format():
    """Source check: format() must include framing_directive as a
    kwarg or the call would KeyError on the placeholder."""
    src = inspect.getsource(compose_manuscript)
    assert "framing_directive=framing_directive" in src
    # The directive is computed via the helper.
    assert "_build_framing_directive(ro_names" in src


# ── Module imports clean ────────────────────────────────────────────────────


def test_drafter_module_imports_clean():
    assert drafter_mod.compose_manuscript is not None
    assert drafter_mod._build_framing_directive is not None
    assert drafter_mod._count_empirical_framing_violations is not None
