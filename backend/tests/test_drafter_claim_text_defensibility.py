"""Tests that the Drafter prompt teaches claim_text must be source-defensible.

Production paper apep_9afaf116 (autonomous-loop run 25217093244) had
PR #65's source excerpts and PR #66's claim_type vs source_type
pairing rules. The Verifier (PR #65) had access to actual source
text. Result: 5 verified + 11 failed + 9 pending = 64% coverage.

Inspecting the 5 verified vs 11 failed pattern, the dividing line is
NOT claim_type or source_type — those rules are followed correctly
in many failed claims. The dividing line is whether claim_text
DESCRIBES the source itself vs USES the source as a hand-wave
citation for a paper-argument.

VERIFIED (passed Verifier):
  - "The Federal Register is the official daily publication for
    rules ..."  + source=federal_register
  - "USAspending.gov is the official source for federal spending
    data ..." + source=usaspending
  - "The NIST AI RMF organizes risk management around four
    functions ..." + source=nist_ai_rmf

FAILED (rejected by Verifier):
  - "Federal agencies deploy AI systems for consequential public
    functions including benefits adjudication" + source=usaspending
  - "Algorithmic systems introduce novel accountability deficits
    including opacity and systematic bias" + source=openalex

Pattern: VERIFIED claims describe the source. FAILED claims use the
source as a citation badge for paper-prose interpretations.

PR #68 adds explicit prompt guidance with concrete bad/good examples
drawn from this paper.

This file locks in:
  * Prompt has a "claim_text must be source-defensible" section
  * The verified examples from apep_9afaf116 are named
  * The failed examples from apep_9afaf116 are named
  * The remediation rule (describe the source, not the world via it)
    is stated
"""

from __future__ import annotations

from app.services.paper_generation.roles.drafter import DRAFT_USER_PROMPT


def test_prompt_has_claim_text_defensibility_section():
    """Lock in that the new section exists."""
    assert "claim_text must be source-defensible" in DRAFT_USER_PROMPT


def test_prompt_references_apep_9afaf116():
    """Trace future-self back to the production paper that motivated
    this rule."""
    assert "apep_9afaf116" in DRAFT_USER_PROMPT


def test_prompt_distinguishes_argument_from_claim():
    """The prompt must make explicit that paper prose != claim
    evidence. Without this distinction the LLM keeps writing argument-
    sentences as claim_text."""
    flat = " ".join(DRAFT_USER_PROMPT.split())
    assert "argument lives in" in flat or "argument" in flat.lower()
    assert "evidence" in flat.lower()


def test_prompt_provides_concrete_verified_examples():
    """Concrete examples are more memorable than abstract rules.
    Reference at least one of the actual passing claims."""
    # The "describes what the source IS" example.
    assert "Federal Register is the official daily publication" in DRAFT_USER_PROMPT


def test_prompt_provides_concrete_failed_examples():
    """The exact failure phrasing must appear so the LLM matches and
    avoids the pattern."""
    # apep_9afaf116's most-cited failed claim.
    assert "Federal agencies deploy AI systems for consequential" in DRAFT_USER_PROMPT
    # The 'openalex' bibliographic-database overuse.
    assert "novel accountability deficits" in DRAFT_USER_PROMPT


def test_prompt_states_remediation():
    """The fix is concrete: describe the source's own content or a
    specific cited work; do NOT assert world-facts via a database
    that merely contains records."""
    flat = " ".join(DRAFT_USER_PROMPT.split())
    assert "describes either" in flat or "describes" in flat
    assert "specific cited work" in flat.lower() or "specific" in flat.lower()
    # The 'records' pattern that turns FAILED into VERIFIED.
    assert "records" in flat.lower()
