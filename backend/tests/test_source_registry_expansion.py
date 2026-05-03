"""Tests for the source registry expansion (PR #70).

Production paper apep_9afaf116 (autonomous-loop run 25217093244) was
about federal AI procurement audit clauses. The Drafter wanted to
make claims about federal AI deployment patterns and could not find
a registered source for them — USAspending has spending records,
not deployment claims; Federal Register has rule text, not agency
practice.

The registry was 18 sources at that point, narrow for AI-governance
research. The reflection doc (.claude/autodevelop-reflection-
2026-05-01.md) flagged "Source registry expansion" as item D —
"data work, not code". This PR adds 6 high-leverage Tier A sources
that close specific gaps observed in production papers:

  - federal_ai_use_cases: agencies' EO 13960 AI use case inventories
  - gao_reports: GAO audits of federal AI use
  - whitehouse_ostp: executive orders / OMB AI memoranda
  - uspto_patents: AI patent filings and grants
  - arxiv: AI/ML preprints (specific cited works, not just openalex)
  - (one more pre-existing here for clarity)

This file locks in:
  * The 6 new Tier A sources are present in SOURCE_CARDS
  * Each has the required schema fields the Data Steward / Drafter rely on
  * Tier counts are at least the post-PR levels
  * No source ID collisions (would silently overwrite an entry)
"""

from __future__ import annotations

import json

from seeds.source_cards import SOURCE_CARDS

# ── Required new sources ───────────────────────────────────────────────────

NEW_TIER_A_IDS = {
    "federal_ai_use_cases",
    "gao_reports",
    "whitehouse_ostp",
    "uspto_patents",
    "arxiv",
}


def test_new_sources_are_present():
    """All 5 newly-added Tier A sources must be in the seed list."""
    seeded_ids = {sc["id"] for sc in SOURCE_CARDS}
    missing = NEW_TIER_A_IDS - seeded_ids
    assert not missing, f"Missing newly-added source IDs: {missing}"


def test_new_sources_are_tier_a():
    """All new sources are tagged as Tier A — they are
    audited/canonical authorities suitable for empirical/doctrinal
    claims. Lower-tier classification would be wrong and would let
    the Drafter anchor central claims to them after PR #55."""
    by_id = {sc["id"]: sc for sc in SOURCE_CARDS}
    for new_id in NEW_TIER_A_IDS:
        assert by_id[new_id]["tier"] == "A", (
            f"{new_id} should be Tier A — change the seed entry or revisit "
            "whether it should anchor central claims at all."
        )


def test_new_sources_are_active():
    """Inactive sources are filtered out of the Drafter's prompt
    (PR #55 closed-set listing). All new entries are live."""
    by_id = {sc["id"]: sc for sc in SOURCE_CARDS}
    for new_id in NEW_TIER_A_IDS:
        assert by_id[new_id]["active"] is True, (
            f"{new_id} is inactive — it won't appear in the Drafter's prompt "
            "and would be effectively unregistered."
        )


# ── Schema correctness ─────────────────────────────────────────────────────


def test_each_new_source_has_required_fields():
    """The Data Steward / Drafter / source_registry code expects
    these columns to be set. A missing field would not surface until
    a paper actually tried to use the source."""
    by_id = {sc["id"]: sc for sc in SOURCE_CARDS}
    required_keys = {
        "id",
        "name",
        "url",
        "tier",
        "source_type",
        "access_method",
        "claim_permissions",
        "claim_prohibitions",
        "known_traps",
        "fragility_score",
        "active",
    }
    for new_id in NEW_TIER_A_IDS:
        card = by_id[new_id]
        missing = required_keys - card.keys()
        assert not missing, f"{new_id} missing fields: {missing}"


def test_claim_permissions_are_valid_json_lists():
    """The source_registry parses these as JSON. A malformed value
    would explode in production, not in seed."""
    by_id = {sc["id"]: sc for sc in SOURCE_CARDS}
    for new_id in NEW_TIER_A_IDS:
        for field in ("claim_permissions", "claim_prohibitions", "known_traps"):
            value = by_id[new_id][field]
            parsed = json.loads(value)
            assert isinstance(parsed, list), (
                f"{new_id}.{field} must be a JSON list, got {type(parsed).__name__}"
            )
            assert all(isinstance(x, str) for x in parsed), (
                f"{new_id}.{field} must contain only strings"
            )
            assert len(parsed) > 0, (
                f"{new_id}.{field} is an empty list — every Tier A source "
                "should articulate at least one permission/prohibition/trap"
            )


def test_fragility_score_is_in_range():
    """Used as a heuristic by source_registry; values must be in
    [0, 1] or downstream comparisons go wrong."""
    by_id = {sc["id"]: sc for sc in SOURCE_CARDS}
    for new_id in NEW_TIER_A_IDS:
        score = by_id[new_id]["fragility_score"]
        assert 0.0 <= score <= 1.0, f"{new_id}.fragility_score = {score} (must be in [0, 1])"


# ── Integrity ──────────────────────────────────────────────────────────────


def test_no_duplicate_ids_in_seed_list():
    """Two entries with the same id silently overwrite each other on
    seed re-run; the second one wins. Adding a new entry with the
    same id as an existing one would be a real footgun."""
    ids = [sc["id"] for sc in SOURCE_CARDS]
    duplicates = [i for i in set(ids) if ids.count(i) > 1]
    assert not duplicates, f"Duplicate source IDs: {duplicates}"


def test_total_source_count_at_or_above_expansion():
    """Lock in the post-PR-#70 count. If this drops, an entry was
    deleted — investigate before merging."""
    assert len(SOURCE_CARDS) >= 23, (
        f"Expected >=23 source cards (18 pre-PR + 5 added), got {len(SOURCE_CARDS)}."
    )


def test_tier_a_count_at_or_above_expansion():
    """Specifically, Tier A grew from 9 to 14. Tier A sources are
    the only ones that can anchor central (empirical/doctrinal)
    claims per PR #55, so growth here directly reduces the rate of
    fabricated source IDs."""
    tier_a_count = sum(1 for sc in SOURCE_CARDS if sc["tier"] == "A")
    assert tier_a_count >= 14, (
        f"Expected >=14 Tier A sources (9 pre-PR + 5 added), got {tier_a_count}."
    )
