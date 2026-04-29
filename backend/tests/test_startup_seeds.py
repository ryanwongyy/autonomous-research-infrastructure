"""Regression tests: source cards must be seeded on app startup.

Background: production run #25131261938 had both papers reach the Data
Steward stage and die with::

    LLM picked 10 unregistered source IDs and the fallback whitelist
    was empty.

The fallback whitelist (federal_register + regulations_gov) was empty
because the production database had **zero** source cards seeded.
Render's deploy never ran ``python -m seeds.source_cards``, so even
though PR #17 added a fallback, there were no registered IDs to fall
back to.

The fix wires both seed runners into ``lifespan`` in ``app/main.py``.
These tests guard the contract so a future refactor doesn't silently
skip seeding again.
"""

from __future__ import annotations

import inspect

from seeds.source_cards import SOURCE_CARDS, seed_source_cards


def test_source_cards_seed_list_is_non_empty():
    """The data file backing seed_source_cards must contain rows."""
    assert isinstance(SOURCE_CARDS, list)
    assert len(SOURCE_CARDS) >= 10, (
        f"Expected >=10 registered source cards, got {len(SOURCE_CARDS)}. "
        "If this drops, the Data Steward stage has nowhere to fall back to."
    )


def test_fallback_whitelist_ids_are_in_seed_list():
    """The Data Steward stage falls back to these IDs when the LLM
    hallucinates. They MUST be in the seed list.
    """
    seeded_ids = {sc["id"] for sc in SOURCE_CARDS}
    required = {"federal_register", "regulations_gov"}
    missing = required - seeded_ids
    assert not missing, (
        f"Data Steward fallback IDs {missing} are not in the seed list. "
        "Either re-add them to seeds/source_cards.py or update the "
        "fallback whitelist in orchestrator._stage_data_steward."
    )


def test_seed_source_cards_is_async_callable():
    """If seed_source_cards stops being async, the lifespan await
    sites in app/main.py break silently.
    """
    assert inspect.iscoroutinefunction(seed_source_cards)


def test_lifespan_imports_seed_functions():
    """A regression for the literal lines added in app/main.py.

    If a future refactor removes the seed call from lifespan, the
    Data Steward stage will start failing again the moment Render
    spins up a fresh DB. This test reads the source of lifespan and
    asserts the seed calls are still there.
    """
    from app.main import lifespan

    src = inspect.getsource(lifespan)
    assert "seed_source_cards" in src, (
        "lifespan no longer calls seed_source_cards. A fresh DB will "
        "have no registered source cards and the Data Steward stage "
        "will fail with an empty fallback whitelist."
    )
    assert "seed_families" in src, "lifespan no longer calls seed_families."
