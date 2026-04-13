"""Verifies that paper claims are properly backed by sources or results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_map import ClaimMap
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.services.provenance.source_registry import (
    CENTRAL_CLAIM_TYPES,
    SNAPSHOT_FRESHNESS_DAYS,
    validate_claim_against_source,
)

logger = logging.getLogger(__name__)


async def verify_paper_claims(session: AsyncSession, paper_id: str) -> dict:
    """Verify all claims for a paper.

    Returns a comprehensive verification report including coverage ratio,
    tier violations, stale sources, and an overall pass/fail verdict.
    """
    # Fetch all claims for this paper.
    stmt = select(ClaimMap).where(ClaimMap.paper_id == paper_id)
    result = await session.execute(stmt)
    claims: list[ClaimMap] = list(result.scalars().all())

    total_claims = len(claims)

    if total_claims == 0:
        return {
            "paper_id": paper_id,
            "total_claims": 0,
            "verified": 0,
            "failed": 0,
            "pending": 0,
            "coverage_ratio": 0.0,
            "unlinked_claims": [],
            "tier_violations": [],
            "stale_sources": [],
            "passed": False,
        }

    verified = 0
    failed = 0
    pending = 0
    unlinked_claims: list[str] = []
    tier_violations: list[dict] = []
    stale_sources: list[dict] = []

    for claim in claims:
        # --- Tally verification status ---
        status = claim.verification_status
        if status == "verified":
            verified += 1
        elif status == "failed":
            failed += 1
        else:
            pending += 1

        # --- Check if claim is linked to a source or result ---
        has_source = claim.source_card_id is not None
        has_result = claim.result_object_ref is not None
        if not has_source and not has_result:
            unlinked_claims.append(
                f"claim_id={claim.id}: {claim.claim_text[:80]}"
            )
            continue

        # --- Source-card-level checks ---
        if has_source:
            source_card = await _get_source_card(session, claim.source_card_id)
            if source_card is None:
                tier_violations.append({
                    "claim_id": claim.id,
                    "claim_type": claim.claim_type,
                    "source_card_id": claim.source_card_id,
                    "violation": "Source card not found in database.",
                })
                continue

            # Tier C anchoring central claims
            if (
                source_card.tier.upper() == "C"
                and claim.claim_type.lower() in CENTRAL_CLAIM_TYPES
            ):
                tier_violations.append({
                    "claim_id": claim.id,
                    "claim_type": claim.claim_type,
                    "source_card_id": claim.source_card_id,
                    "source_tier": "C",
                    "violation": (
                        f"Tier C source '{source_card.name}' anchoring "
                        f"central claim type '{claim.claim_type}'."
                    ),
                })

            # Validate claim type against source permissions
            validation = await validate_claim_against_source(
                source_card, claim.claim_text, claim.claim_type
            )
            if not validation["valid"]:
                tier_violations.append({
                    "claim_id": claim.id,
                    "claim_type": claim.claim_type,
                    "source_card_id": claim.source_card_id,
                    "source_tier": source_card.tier,
                    "violation": validation["reason"],
                })

            # Check linked snapshot freshness if a snapshot is referenced
            if claim.source_snapshot_id is not None:
                snapshot = await _get_snapshot(session, claim.source_snapshot_id)
                if snapshot is not None:
                    staleness = _check_snapshot_staleness(snapshot)
                    if not staleness["fresh"]:
                        stale_sources.append({
                            "claim_id": claim.id,
                            "source_card_id": claim.source_card_id,
                            "snapshot_id": snapshot.id,
                            "fetched_at": str(snapshot.fetched_at),
                            "days_stale": staleness["days_stale"],
                        })

    coverage_ratio = verified / total_claims if total_claims > 0 else 0.0

    return {
        "paper_id": paper_id,
        "total_claims": total_claims,
        "verified": verified,
        "failed": failed,
        "pending": pending,
        "coverage_ratio": round(coverage_ratio, 4),
        "unlinked_claims": unlinked_claims,
        "tier_violations": tier_violations,
        "stale_sources": stale_sources,
        "passed": coverage_ratio >= 1.0 and len(tier_violations) == 0,
    }


async def verify_single_claim(session: AsyncSession, claim_id: int) -> dict:
    """Verify a single claim map entry.

    Returns a verification result dict with the claim's status, source
    validation, and any issues found.
    """
    stmt = select(ClaimMap).where(ClaimMap.id == claim_id)
    result = await session.execute(stmt)
    claim: ClaimMap | None = result.scalar_one_or_none()

    if claim is None:
        return {
            "claim_id": claim_id,
            "found": False,
            "error": "Claim not found.",
        }

    issues: list[str] = []

    # Check linkage
    has_source = claim.source_card_id is not None
    has_result = claim.result_object_ref is not None
    if not has_source and not has_result:
        issues.append("Claim is not linked to any source card or result object.")

    source_validation: dict | None = None
    snapshot_freshness: dict | None = None

    if has_source:
        source_card = await _get_source_card(session, claim.source_card_id)
        if source_card is None:
            issues.append(
                f"Source card '{claim.source_card_id}' not found in database."
            )
        else:
            source_validation = await validate_claim_against_source(
                source_card, claim.claim_text, claim.claim_type
            )
            if not source_validation["valid"]:
                issues.append(source_validation["reason"])

            # Check snapshot freshness
            if claim.source_snapshot_id is not None:
                snapshot = await _get_snapshot(session, claim.source_snapshot_id)
                if snapshot is None:
                    issues.append(
                        f"Referenced snapshot {claim.source_snapshot_id} not found."
                    )
                else:
                    snapshot_freshness = _check_snapshot_staleness(snapshot)
                    if not snapshot_freshness["fresh"]:
                        issues.append(
                            f"Linked snapshot is {snapshot_freshness['days_stale']} "
                            f"days old (threshold: {SNAPSHOT_FRESHNESS_DAYS})."
                        )

    return {
        "claim_id": claim.id,
        "found": True,
        "paper_id": claim.paper_id,
        "claim_type": claim.claim_type,
        "claim_text": claim.claim_text[:200],
        "verification_status": claim.verification_status,
        "source_card_id": claim.source_card_id,
        "source_snapshot_id": claim.source_snapshot_id,
        "has_result_ref": has_result,
        "source_validation": source_validation,
        "snapshot_freshness": snapshot_freshness,
        "issues": issues,
        "valid": len(issues) == 0,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_source_card(
    session: AsyncSession, source_card_id: str
) -> SourceCard | None:
    """Fetch a source card by ID."""
    stmt = select(SourceCard).where(SourceCard.id == source_card_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_snapshot(
    session: AsyncSession, snapshot_id: int
) -> SourceSnapshot | None:
    """Fetch a source snapshot by ID."""
    stmt = select(SourceSnapshot).where(SourceSnapshot.id == snapshot_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _check_snapshot_staleness(snapshot: SourceSnapshot) -> dict:
    """Check if a snapshot is stale based on its fetch date."""
    now = datetime.now(timezone.utc)
    fetched = snapshot.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)

    delta = now - fetched
    days_stale = delta.days
    return {
        "fresh": days_stale <= SNAPSHOT_FRESHNESS_DAYS,
        "days_stale": days_stale,
    }
