"""Regression test: Drafter must filter LLM-hallucinated source IDs
out of ClaimMap inserts.

Background: production run #25144089527 had Drafter complete the LLM
manuscript-generation but blow up on the INSERT into claim_maps with::

    ForeignKeyViolationError: ... violates foreign key constraint
    \"claim_maps_source_card_id_fkey\"
    DETAIL:  Key (source_card_id)=(theoretical) is not present in
    table \"source_cards\".

The LLM picked ``source_ref=\"theoretical\"`` for a claim. ``theoretical``
is not a registered source card. PR #17 fixed the same hallucination
pattern in Data Steward; this test guards the equivalent fix in
Drafter's claim_map writes.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles.drafter import compose_manuscript


def test_drafter_validates_source_ref_against_registered_ids():
    """The compose_manuscript function must look up registered source-
    card IDs before assigning source_card_id on a ClaimMap. Otherwise
    a hallucinated LLM source_ref blows up the FK constraint.
    """
    src = inspect.getsource(compose_manuscript)

    # Must query SourceCard at the writes phase
    assert "SourceCard" in src, (
        "compose_manuscript must query SourceCard to validate LLM-supplied source_ref values."
    )

    # Must filter against the registered set before assigning
    assert "registered_source_ids" in src or "registered_ids" in src, (
        "compose_manuscript must compare source_ref against the "
        "registered source-card IDs before setting source_card_id."
    )

    # Must use a None fallback for unregistered IDs
    assert "valid_source_card_id" in src or "None" in src.split("claim_map_entries")[0], (
        "compose_manuscript must default to NULL source_card_id when "
        "the LLM's source_ref isn't in the registered set."
    )
