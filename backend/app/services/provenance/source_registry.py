"""CRUD and validation for source cards."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# Claim types considered "central" (empirical or doctrinal backbone claims).
# Tier C sources cannot anchor these -- only auxiliary/corroboration roles.
CENTRAL_CLAIM_TYPES = {"empirical", "doctrinal"}

# The full set of methodological claim_type values the pipeline emits.
# Used to disambiguate `source_card.claim_permissions` data shape: when
# a source's permissions list contains ANY of these strings, the list
# is being used to gate by claim-type. When it contains NONE, the list
# is using the older "scope/topic" semantics (e.g. "spending", "vendor
# concentration") and Rule 3's claim_type-vs-permissions comparison is
# meaningless — every comparison would falsely fail.
KNOWN_CLAIM_TYPES = {
    "empirical",
    "descriptive",
    "doctrinal",
    "theoretical",
    "historical",
}

# Maximum days before a snapshot is considered stale.
SNAPSHOT_FRESHNESS_DAYS = 30


async def get_source_card(
    session: AsyncSession, source_id: str
) -> SourceCard | None:
    """Fetch a single source card by its ID, eagerly loading snapshots."""
    stmt = (
        select(SourceCard)
        .where(SourceCard.id == source_id)
        .options(selectinload(SourceCard.snapshots))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_source_cards(
    session: AsyncSession,
    tier: str | None = None,
    active_only: bool = True,
) -> list[SourceCard]:
    """List source cards, optionally filtered by tier and active status."""
    stmt = select(SourceCard).options(selectinload(SourceCard.snapshots))

    if active_only:
        stmt = stmt.where(SourceCard.active.is_(True))
    if tier is not None:
        stmt = stmt.where(SourceCard.tier == tier.upper())

    stmt = stmt.order_by(SourceCard.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def validate_claim_against_source(
    source_card: SourceCard,
    claim_text: str,
    claim_type: str,
) -> dict:
    """Validate whether a claim is compatible with a source card.

    Checks:
    1. claim_type is listed in the source's claim_permissions.
    2. claim_type is NOT listed in the source's claim_prohibitions.
    3. Tier C sources may not anchor central (empirical/doctrinal) claims.

    Returns a dict with validation result and reasoning.
    """
    tier = source_card.tier.upper()

    # Parse JSON permission/prohibition lists from the source card.
    permissions: list[str] = safe_json_loads(source_card.claim_permissions, [])
    prohibitions: list[str] = safe_json_loads(source_card.claim_prohibitions, [])

    # Parse required_corroboration configuration.
    corroboration_config: dict = safe_json_loads(source_card.required_corroboration, {})

    # Determine whether the source requires corroboration for this claim type.
    requires_corroboration = claim_type in corroboration_config.get("claim_types", [])

    # -- Rule 1: Tier C restriction on central claims --
    if tier == "C" and claim_type.lower() in CENTRAL_CLAIM_TYPES:
        return {
            "valid": False,
            "reason": (
                f"Tier C source '{source_card.name}' cannot anchor central "
                f"({claim_type}) claims. Tier C sources may only support "
                "auxiliary or corroboration claims."
            ),
            "tier": tier,
            "requires_corroboration": True,
        }

    # The seed data ships ``claim_permissions`` and ``claim_prohibitions``
    # as scope/topic descriptors (e.g. "spending", "vendor concentration",
    # "compliance or effects by themselves") rather than methodological
    # claim_type values. Rules 2 and 3 below were written to compare
    # ``claim_type`` against these lists, which means they always fire
    # for every claim from any source whose lists are topic-shaped — i.e.
    # all current production sources. Production paper apep_703f59f7's L2
    # review hit 22 spurious tier_violations on this exact path
    # (descriptive vs ['spending', ...]).
    #
    # We detect topic-shape by checking overlap with KNOWN_CLAIM_TYPES.
    # When a source's lists have NO overlap, we treat them as topic-shaped
    # and skip the claim-type comparison. This preserves the type-gating
    # contract for any future source that ships actual claim_types.
    permissions_are_typed = any(
        p.lower() in KNOWN_CLAIM_TYPES for p in permissions
    )
    prohibitions_are_typed = any(
        p.lower() in KNOWN_CLAIM_TYPES for p in prohibitions
    )

    # -- Rule 2: Explicit prohibition --
    if prohibitions_are_typed and claim_type.lower() in [
        p.lower() for p in prohibitions
    ]:
        return {
            "valid": False,
            "reason": (
                f"Claim type '{claim_type}' is explicitly prohibited by "
                f"source '{source_card.name}' (prohibitions: {prohibitions})."
            ),
            "tier": tier,
            "requires_corroboration": requires_corroboration,
        }

    # -- Rule 3: Not in permissions list (if the list is non-empty AND
    #    contains claim-type semantics; topic-shaped lists are skipped) --
    if (
        permissions
        and permissions_are_typed
        and claim_type.lower() not in [p.lower() for p in permissions]
    ):
        return {
            "valid": False,
            "reason": (
                f"Claim type '{claim_type}' is not in the allowed permissions "
                f"for source '{source_card.name}' (permissions: {permissions})."
            ),
            "tier": tier,
            "requires_corroboration": requires_corroboration,
        }

    return {
        "valid": True,
        "reason": (
            f"Claim type '{claim_type}' is permitted by source "
            f"'{source_card.name}' (Tier {tier})."
        ),
        "tier": tier,
        "requires_corroboration": requires_corroboration,
    }


async def check_source_freshness(
    session: AsyncSession, source_id: str
) -> dict:
    """Check whether a source has a recent snapshot.

    Returns:
        {
            "fresh": bool,
            "last_snapshot": datetime | None,
            "days_stale": int | None,
        }
    """
    stmt = (
        select(SourceSnapshot)
        .where(SourceSnapshot.source_card_id == source_id)
        .order_by(SourceSnapshot.fetched_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    latest: SourceSnapshot | None = result.scalar_one_or_none()

    if latest is None:
        return {
            "fresh": False,
            "last_snapshot": None,
            "days_stale": None,
        }

    now = datetime.now(timezone.utc)
    fetched = latest.fetched_at
    # Ensure timezone-aware comparison.
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)

    delta = now - fetched
    days_stale = delta.days

    return {
        "fresh": days_stale <= SNAPSHOT_FRESHNESS_DAYS,
        "last_snapshot": latest.fetched_at,
        "days_stale": days_stale,
    }
