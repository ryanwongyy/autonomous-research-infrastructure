"""Tests that the Drafter's prompt presents registered SourceCards as
a closed set the LLM must pick from.

Production paper apep_703f59f7 (autonomous-loop run 25184049337) had
21/25 claims soft-linked: the LLM picked source IDs like "29 CFR §
1607.4(d)" or "Griggs v. Duke Power" that aren't in the SourceCard
registry. PR #36's soft-fallback preserved provenance for review,
PR #45 made L1 accept those, but the underlying quality was poor —
each claim's `source_card_id` stayed NULL.

This PR enriches the Drafter prompt to:

  - List every active registered SourceCard ID (with name as
    disambiguation) as a closed set.
  - List every result-object name from the manifest.
  - Tell the LLM "source_ref MUST be from these lists" with examples
    of what NOT to do (free-text legal authorities).

These tests lock in the prompt structure + the source-ID load.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles import drafter as drafter_mod
from app.services.paper_generation.roles.drafter import (
    DRAFT_USER_PROMPT,
    compose_manuscript,
)


# ── Prompt template includes new sections ───────────────────────────────────


def test_prompt_lists_registered_source_cards():
    assert "REGISTERED SOURCE CARDS" in DRAFT_USER_PROMPT
    assert "{registered_source_ids}" in DRAFT_USER_PROMPT


def test_prompt_lists_registered_result_objects():
    assert "REGISTERED RESULT OBJECTS" in DRAFT_USER_PROMPT
    assert "{registered_result_object_names}" in DRAFT_USER_PROMPT


def test_prompt_has_critical_source_linkage_section():
    """The strong instruction tells the LLM the registered lists are
    closed — no inventing references."""
    assert "CRITICAL" in DRAFT_USER_PROMPT
    # Tells the LLM the IDs come from the lists above
    assert "MUST be either" in DRAFT_USER_PROMPT
    # Forbids free-text legal authorities — calls out the production failure
    assert "Do NOT invent source IDs" in DRAFT_USER_PROMPT


def test_prompt_provides_doctrinal_clarification():
    """Doctrinal claims often want to cite legal authorities. Make
    sure the prompt clarifies: prose can mention them, but the
    ClaimMap source_ref must still resolve to a registered item."""
    assert "Doctrinal/legal claims" in DRAFT_USER_PROMPT


# ── Phase 1 loads source IDs ─────────────────────────────────────────────────


def test_compose_manuscript_loads_source_card_ids_in_phase1():
    """Source inspection: the read-phase block must query SourceCard
    so the prompt can list the closed set."""
    src = inspect.getsource(compose_manuscript)
    # Phase 1 marker
    assert "Phase 1" in src
    # Query for source cards
    assert "SourceCard" in src
    # Must filter to active sources only
    assert "SourceCard.active.is_(True)" in src
    # Must build the prompt-ready string
    assert "registered_source_ids_str" in src or "registered_source_pairs" in src


def test_compose_manuscript_extracts_result_object_names():
    """The manifest's `result_objects` dict's keys become the closed
    set of valid result_object source_refs."""
    src = inspect.getsource(compose_manuscript)
    assert 'result_manifest["result_objects"]' in src or "result_objects" in src
    # Names extracted explicitly so the prompt can show them
    assert "ro_names" in src or "result_object_names" in src


def test_compose_manuscript_passes_both_lists_to_format():
    """Source check: the format() call passes both new template keys."""
    src = inspect.getsource(compose_manuscript)
    assert "registered_source_ids=" in src
    assert "registered_result_object_names=" in src


# ── Empty-registry fallbacks ─────────────────────────────────────────────────


def test_compose_manuscript_handles_empty_source_registry():
    """When no SourceCards are registered (fresh deployment), the
    prompt must still format successfully — show a clear placeholder
    instead of crashing. PR #55 changed the format to per-tier
    placeholders ("no Tier A sources registered" etc)."""
    src = inspect.getsource(compose_manuscript)
    # Look for the placeholder fallback string (any of the per-tier
    # variants since PR #55).
    assert (
        "no source cards registered yet" in src
        or "(no source cards" in src
        or "no Tier" in src
    )


def test_compose_manuscript_handles_empty_result_manifest():
    src = inspect.getsource(compose_manuscript)
    assert "no result objects registered yet" in src or "(no result objects" in src


# ── Module imports clean ─────────────────────────────────────────────────────


def test_module_imports_clean():
    assert drafter_mod.compose_manuscript is not None
    assert drafter_mod.DRAFT_USER_PROMPT is not None
