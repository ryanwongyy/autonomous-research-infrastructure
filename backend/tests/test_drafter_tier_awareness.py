"""Tests that the Drafter prompt enforces tier-vs-claim_type pairing.

Production paper apep_3ddffa34 (autonomous-loop run 25202085464) was
generated with PR #51's closed source set (25/25 hard-linked) and
passed L1 structural review. But L2 fired 14 CRITICAL
``tier_violation`` issues because the Drafter anchored 8 empirical
claims to a Tier C source ("OECD AI Incidents Monitor"). Tier C
sources cannot anchor central (empirical/doctrinal) claims —
that's the long-standing research-design rule the validator enforces.

The Drafter's prompt previously listed sources as a flat closed set
without tier annotation, so the LLM didn't see the tier constraint
when picking source_ref for an empirical claim.

PR #55 groups sources by tier in the prompt so the structural
constraint is visible at the point where the LLM picks a source.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles.drafter import (
    DRAFT_USER_PROMPT,
    compose_manuscript,
)

# ── Prompt content: tier sections are present and labelled ──────────────────


def test_prompt_lists_sources_grouped_by_tier():
    """The prompt's REGISTERED SOURCE CARDS section must label each tier
    explicitly so the LLM sees the structural distinction."""
    src = inspect.getsource(compose_manuscript)
    # Per-tier headings must be in the constructed string.
    assert "TIER A" in src
    assert "TIER B" in src
    assert "TIER C" in src


def test_prompt_states_tier_a_b_suitable_for_empirical():
    """The Tier A / B labels must explicitly call out empirical/doctrinal
    suitability so the LLM understands the pairing."""
    src = inspect.getsource(compose_manuscript)
    # Tier A heading mentions empirical/doctrinal as suitable use.
    assert "SUITABLE for empirical/doctrinal" in src or "empirical or doctrinal" in src


def test_prompt_warns_tier_c_cannot_anchor_central_claims():
    """The Tier C label must spell out the constraint and reference the
    L2 review symptom so the LLM connects it to a real failure path."""
    src = inspect.getsource(compose_manuscript)
    # The constraint must be visible — use 'NEVER' wording and
    # reference 'tier_violation' so the LLM associates the rule with
    # the L2 failure path.
    assert "NEVER" in src
    assert "tier_violation" in src


# ── Prompt: instructions section enforces the pairing rule ───────────────────


def test_prompt_has_explicit_pairing_section():
    """The CRITICAL claim_type vs source TIER pairing section must be
    in the prompt template so the LLM sees the rule at task time, not
    just in the source listing."""
    assert "claim_type vs source TIER pairing" in DRAFT_USER_PROMPT
    # Must mention the production failure for grounding.
    assert "apep_3ddffa34" in DRAFT_USER_PROMPT or "tier_violation" in DRAFT_USER_PROMPT


def test_prompt_forbids_tier_c_for_central_claims():
    """The pairing section must explicitly forbid Tier C for empirical/
    doctrinal claims."""
    assert "Tier C" in DRAFT_USER_PROMPT
    # Must list the auxiliary claim types Tier C IS allowed for.
    assert "descriptive" in DRAFT_USER_PROMPT
    assert "historical" in DRAFT_USER_PROMPT


def test_prompt_recommends_claim_type_diversity():
    """Production paper apep_3ddffa34 had 25/25 empirical claims —
    suspicious uniformity. The prompt should encourage a mix of
    claim types."""
    assert (
        "MIX of claim_types" in DRAFT_USER_PROMPT
        or "all-empirical paper is suspicious" in DRAFT_USER_PROMPT
    )


# ── Phase 1: source-card load fetches tier ──────────────────────────────────


def test_phase1_loads_tier_alongside_id():
    """Source check: the SELECT must include SourceCard.tier so the
    grouping by tier is possible."""
    src = inspect.getsource(compose_manuscript)
    assert "SourceCard.tier" in src, (
        "Phase 1 must SELECT SourceCard.tier to enable per-tier grouping in the prompt."
    )


def test_phase1_groups_sources_into_tier_buckets():
    """Source check: the loop building the prompt-ready string must
    bucket each source into its tier."""
    src = inspect.getsource(compose_manuscript)
    assert "sources_by_tier" in src
