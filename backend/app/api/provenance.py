import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.config import settings
from app.database import get_db
from app.models.paper import Paper
from app.models.claim_map import ClaimMap
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.utils import safe_json_loads, utcnow_naive

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/papers/{paper_id}/claims")
async def list_paper_claims(paper_id: str, db: AsyncSession = Depends(get_db)):
    """List all claims for a paper with their verification status."""
    # Verify paper exists
    paper_result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = paper_result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

    query = (
        select(ClaimMap)
        .where(ClaimMap.paper_id == paper_id)
        .order_by(ClaimMap.id)
        .limit(500)
    )
    result = await db.execute(query)
    claims = result.scalars().all()

    output = []
    for claim in claims:
        output.append(
            {
                "id": claim.id,
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_type,
                "source_card_id": claim.source_card_id,
                "source_snapshot_id": claim.source_snapshot_id,
                "source_span_ref": safe_json_loads(claim.source_span_ref),
                "result_object_ref": safe_json_loads(claim.result_object_ref),
                "verification_status": claim.verification_status,
                "verified_by": claim.verified_by,
                "verified_at": claim.verified_at.isoformat()
                if claim.verified_at
                else None,
                "created_at": claim.created_at.isoformat()
                if claim.created_at
                else None,
            }
        )

    # Summary counts by status — aggregated in SQL
    status_rows = (
        await db.execute(
            select(ClaimMap.verification_status, func.count())
            .where(ClaimMap.paper_id == paper_id)
            .group_by(ClaimMap.verification_status)
        )
    ).all()
    status_counts = {row[0]: row[1] for row in status_rows}

    return {
        "paper_id": paper_id,
        "claims": output,
        "total": len(output),
        "status_summary": status_counts,
    }


@router.get("/papers/{paper_id}/provenance")
async def get_paper_provenance(paper_id: str, db: AsyncSession = Depends(get_db)):
    """Get full provenance report for a paper - claim coverage, tier compliance, source freshness."""
    # Verify paper exists
    paper_result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = paper_result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

    # Fetch claims for this paper (capped at 500 for safety)
    claims_result = await db.execute(
        select(ClaimMap).where(ClaimMap.paper_id == paper_id).limit(500)
    )
    claims = claims_result.scalars().all()

    total_claims = len(claims)
    verified_count = sum(1 for c in claims if c.verification_status == "verified")
    failed_count = sum(1 for c in claims if c.verification_status == "failed")
    pending_count = sum(1 for c in claims if c.verification_status == "pending")
    disputed_count = sum(1 for c in claims if c.verification_status == "disputed")

    # Claim coverage: ratio of claims that have a source linked
    sourced_count = sum(1 for c in claims if c.source_card_id or c.result_object_ref)
    coverage_ratio = sourced_count / total_claims if total_claims > 0 else 0.0

    # Tier compliance: check source tiers for all linked claims
    source_ids = list({c.source_card_id for c in claims if c.source_card_id})
    tier_breakdown = {"A": 0, "B": 0, "C": 0, "unknown": 0}
    if source_ids:
        sources_result = await db.execute(
            select(SourceCard).where(SourceCard.id.in_(source_ids))
        )
        sources_map = {s.id: s for s in sources_result.scalars().all()}
        for claim in claims:
            if claim.source_card_id and claim.source_card_id in sources_map:
                tier = sources_map[claim.source_card_id].tier
                tier_breakdown[tier] = tier_breakdown.get(tier, 0) + 1

    # Source freshness: batch query for latest snapshot per source
    stale_threshold = datetime.now(timezone.utc) - timedelta(
        days=settings.source_stale_days
    )
    stale_sources = []
    fresh_sources = []
    if source_ids:
        snap_results = await db.execute(
            select(
                SourceSnapshot.source_card_id,
                func.max(SourceSnapshot.fetched_at).label("latest_fetched"),
            )
            .where(SourceSnapshot.source_card_id.in_(source_ids))
            .group_by(SourceSnapshot.source_card_id)
        )
        snap_map = {
            row.source_card_id: row.latest_fetched for row in snap_results.all()
        }

        for src_id in source_ids:
            fetched_at = snap_map.get(src_id)
            if fetched_at:
                if fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=timezone.utc)
                if fetched_at < stale_threshold:
                    stale_sources.append(src_id)
                else:
                    fresh_sources.append(src_id)
            else:
                stale_sources.append(src_id)

    return {
        "paper_id": paper_id,
        "paper_title": paper.title,
        "claim_coverage": {
            "total_claims": total_claims,
            "sourced_claims": sourced_count,
            "coverage_ratio": round(coverage_ratio, 3),
        },
        "verification_status": {
            "verified": verified_count,
            "failed": failed_count,
            "pending": pending_count,
            "disputed": disputed_count,
        },
        "tier_compliance": tier_breakdown,
        "source_freshness": {
            "stale_threshold_days": settings.source_stale_days,
            "fresh_sources": fresh_sources,
            "stale_sources": stale_sources,
        },
        "provenance_complete": (
            total_claims > 0
            and pending_count == 0
            and failed_count == 0
            and disputed_count == 0
            and coverage_ratio >= 1.0
            and len(stale_sources) == 0
        ),
    }


@router.post("/papers/{paper_id}/claims/verify")
async def trigger_claim_verification(paper_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger verification of all claims for a paper.

    Checks each pending claim against its linked source snapshot to determine
    whether the source data supports the claim.
    """
    # Verify paper exists
    paper_result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = paper_result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

    # Get all pending claims
    claims_result = await db.execute(
        select(ClaimMap)
        .where(ClaimMap.paper_id == paper_id)
        .where(ClaimMap.verification_status == "pending")
        .limit(500)
    )
    pending_claims = claims_result.scalars().all()

    if not pending_claims:
        return {
            "paper_id": paper_id,
            "message": "No pending claims to verify",
            "verified": 0,
            "failed": 0,
            "skipped": 0,
        }

    verified = 0
    failed = 0
    skipped = 0

    # Batch-load all referenced snapshots
    snapshot_ids = list(
        {c.source_snapshot_id for c in pending_claims if c.source_snapshot_id}
    )
    snapshot_map: dict[int, bool] = {}
    if snapshot_ids:
        snap_results = await db.execute(
            select(SourceSnapshot.id, SourceSnapshot.snapshot_hash).where(
                SourceSnapshot.id.in_(snapshot_ids)
            )
        )
        snapshot_map = {row.id: bool(row.snapshot_hash) for row in snap_results.all()}

    # claim.verified_at is TIMESTAMP WITHOUT TIME ZONE on Postgres;
    # use utcnow_naive() for the assignments below.
    now = utcnow_naive()
    for claim in pending_claims:
        if not claim.source_card_id and not claim.result_object_ref:
            skipped += 1
            continue

        if claim.source_card_id and claim.source_snapshot_id:
            has_valid_hash = snapshot_map.get(claim.source_snapshot_id, False)
            if has_valid_hash:
                claim.verification_status = "verified"
                claim.verified_by = "auto:provenance_check"
                claim.verified_at = now
                verified += 1
            else:
                claim.verification_status = "failed"
                claim.verified_by = "auto:provenance_check"
                claim.verified_at = now
                failed += 1
        elif claim.result_object_ref:
            claim.verification_status = "verified"
            claim.verified_by = "auto:provenance_check"
            claim.verified_at = now
            verified += 1
        else:
            skipped += 1

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to persist claim verification for paper %s", paper_id)
        raise HTTPException(
            status_code=500, detail="Failed to persist claim verification results"
        )

    return {
        "paper_id": paper_id,
        "message": "Claim verification complete",
        "verified": verified,
        "failed": failed,
        "skipped": skipped,
    }
