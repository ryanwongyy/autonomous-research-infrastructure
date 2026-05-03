"""Tests that ``validate_claim_against_source`` distinguishes between
topic-shaped and type-shaped ``claim_permissions`` lists.

Production paper apep_703f59f7 reached L2 review with 22 CRITICAL
``tier_violation`` issues whose messages all looked like::

    Claim type 'descriptive' is not in the allowed permissions for
    source 'USAspending.gov' (permissions: ['spending', 'vendor
    concentration', 'contract design', 'safeguard language',
    'diffusion of guardrails']).

The seed data ships ``claim_permissions`` as scope/topic descriptors
(e.g. "spending", "vendor concentration") rather than methodological
claim_type values. Rule 3's straight-string comparison between the
claim's claim_type ("descriptive") and the topic list always fails.

This file locks in the disambiguation: the validator detects whether
the permissions list contains ANY known claim_type (empirical /
descriptive / doctrinal / theoretical / historical). When NO overlap,
treat the list as topic-shaped and skip Rule 3. The Tier-C central-
claim rule (Rule 1) keeps firing — that's a real semantic gate.
"""

from __future__ import annotations

import json

import pytest

from app.models.source_card import SourceCard
from app.services.provenance.source_registry import (
    KNOWN_CLAIM_TYPES,
    validate_claim_against_source,
)


def _src(
    name: str,
    *,
    tier: str = "A",
    permissions: list[str] | None = None,
    prohibitions: list[str] | None = None,
) -> SourceCard:
    return SourceCard(
        id=f"SC_{name.replace(' ', '_')}",
        name=name,
        tier=tier,
        source_type="document",
        access_method="manual",
        claim_permissions=json.dumps(permissions or []),
        claim_prohibitions=json.dumps(prohibitions or []),
        required_corroboration="{}",
        active=True,
    )


# ── Constant: KNOWN_CLAIM_TYPES has the right shape ──────────────────────────


def test_known_claim_types_set_matches_pipeline():
    """The disambiguation set must match the claim_type values the
    Drafter / Verifier emit. If a future role adds a new claim_type,
    that role's prompt schema and KNOWN_CLAIM_TYPES must update
    together."""
    assert {
        "empirical",
        "descriptive",
        "doctrinal",
        "theoretical",
        "historical",
    } == KNOWN_CLAIM_TYPES


# ── Topic-shaped permissions: Rule 3 must NOT fire ───────────────────────────


@pytest.mark.asyncio
async def test_topic_shaped_permissions_skip_rule3():
    """Production failure mode: permissions list is topic-based (no
    intersection with KNOWN_CLAIM_TYPES). Validation must NOT fire
    Rule 3 — the claim-type comparison is meaningless here."""
    source = _src(
        "USAspending.gov",
        tier="A",
        permissions=[
            "spending",
            "vendor concentration",
            "contract design",
            "safeguard language",
            "diffusion of guardrails",
        ],
    )
    result = await validate_claim_against_source(source, claim_text="x", claim_type="descriptive")
    assert result["valid"], (
        f"Topic-shaped permissions should accept any claim_type. Got: {result.get('reason')}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claim_type",
    ["empirical", "descriptive", "doctrinal", "theoretical", "historical"],
)
async def test_topic_shaped_permissions_accept_every_known_type(claim_type):
    """Sanity sweep across all 5 emitted claim types."""
    source = _src(
        "Federal Register",
        tier="A",
        permissions=["timing of rules", "legal obligations", "governance design"],
    )
    result = await validate_claim_against_source(source, claim_text="x", claim_type=claim_type)
    assert result["valid"]


# ── Type-shaped permissions: Rule 3 still fires ──────────────────────────────


@pytest.mark.asyncio
async def test_type_shaped_permissions_enforce_rule3():
    """If a source DOES use claim_types in its permissions list (mixed
    or pure), Rule 3 must enforce the gate."""
    source = _src(
        "TypedSource",
        tier="A",
        permissions=["empirical", "descriptive"],
    )
    rejected = await validate_claim_against_source(source, claim_text="x", claim_type="doctrinal")
    assert not rejected["valid"], "Type-shaped permissions should still gate by claim_type."
    assert "not in the allowed permissions" in rejected["reason"]

    accepted = await validate_claim_against_source(source, claim_text="x", claim_type="empirical")
    assert accepted["valid"]


@pytest.mark.asyncio
async def test_mixed_shape_permissions_treats_as_typed():
    """If permissions has at least one known claim_type, treat the
    whole list as type-shaped (don't silently degrade to topic mode).
    """
    source = _src(
        "MixedSource",
        tier="A",
        # Mostly topic, but contains 'empirical' — list is treated as typed.
        permissions=["spending", "empirical"],
    )
    rejected = await validate_claim_against_source(source, claim_text="x", claim_type="descriptive")
    assert not rejected["valid"]


# ── Topic-shaped prohibitions: Rule 2 must NOT fire ──────────────────────────


@pytest.mark.asyncio
async def test_topic_shaped_prohibitions_skip_rule2():
    """Same disambiguation for prohibitions: a topic-shaped list does
    not gate claim_type."""
    source = _src(
        "USAspending.gov",
        tier="A",
        permissions=["spending"],
        prohibitions=["compliance or effects by themselves"],
    )
    result = await validate_claim_against_source(source, claim_text="x", claim_type="empirical")
    assert result["valid"]


@pytest.mark.asyncio
async def test_type_shaped_prohibitions_enforce_rule2():
    source = _src(
        "TypedProhSource",
        tier="A",
        permissions=["empirical", "doctrinal"],
        prohibitions=["theoretical"],
    )
    rejected = await validate_claim_against_source(source, claim_text="x", claim_type="theoretical")
    assert not rejected["valid"]
    assert "explicitly prohibited" in rejected["reason"]


# ── Tier C central-claim rule still works ────────────────────────────────────


@pytest.mark.asyncio
async def test_tier_c_central_rule_still_fires():
    """Rule 1 (Tier C cannot anchor central claims) is independent of
    the permissions disambiguation — still fires regardless of
    permissions shape."""
    source = _src(
        "TierC source",
        tier="C",
        permissions=[],  # empty list — neither shape matters
    )
    rejected = await validate_claim_against_source(source, claim_text="x", claim_type="empirical")
    assert not rejected["valid"]
    assert "Tier C" in rejected["reason"]


# ── Empty permissions doesn't trigger Rule 3 ─────────────────────────────────


@pytest.mark.asyncio
async def test_empty_permissions_accepts_any_type():
    """Pre-existing behavior: an empty permissions list means no
    permission gate applies — keep that."""
    source = _src("LooseSource", tier="A", permissions=[])
    result = await validate_claim_against_source(source, claim_text="x", claim_type="empirical")
    assert result["valid"]
