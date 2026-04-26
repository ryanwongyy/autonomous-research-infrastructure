from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.utils import safe_json_loads

router = APIRouter()


@router.get("/sources")
async def list_sources(
    tier: str | None = Query(None, max_length=10),
    active_only: bool = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all source cards, optionally filtered by tier."""
    query = select(SourceCard)
    if active_only:
        query = query.where(SourceCard.active.is_(True))
    if tier:
        query = query.where(SourceCard.tier == tier.upper())
    query = query.order_by(SourceCard.tier, SourceCard.name).offset(offset).limit(limit)
    result = await db.execute(query)
    sources = result.scalars().all()

    output = []
    for src in sources:
        output.append(
            {
                "id": src.id,
                "name": src.name,
                "url": src.url,
                "tier": src.tier,
                "source_type": src.source_type,
                "update_frequency": src.update_frequency,
                "access_method": src.access_method,
                "requires_key": src.requires_key,
                "canonical_unit": src.canonical_unit,
                "claim_permissions": safe_json_loads(src.claim_permissions, []),
                "claim_prohibitions": safe_json_loads(src.claim_prohibitions, []),
                "fragility_score": src.fragility_score,
                "active": src.active,
            }
        )

    return {"sources": output, "total": len(output)}


@router.get("/sources/{source_id}")
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed source card with claim permissions/prohibitions."""
    result = await db.execute(select(SourceCard).where(SourceCard.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "tier": source.tier,
        "source_type": source.source_type,
        "temporal_coverage": safe_json_loads(source.temporal_coverage),
        "geographic_coverage": safe_json_loads(source.geographic_coverage, []),
        "update_frequency": source.update_frequency,
        "access_method": source.access_method,
        "requires_key": source.requires_key,
        "legal_basis": source.legal_basis,
        "canonical_unit": source.canonical_unit,
        "claim_permissions": safe_json_loads(source.claim_permissions, []),
        "claim_prohibitions": safe_json_loads(source.claim_prohibitions, []),
        "required_corroboration": safe_json_loads(source.required_corroboration),
        "parse_method": source.parse_method,
        "content_hash": source.content_hash,
        "fragility_score": source.fragility_score,
        "retention_policy": source.retention_policy,
        "known_traps": safe_json_loads(source.known_traps, []),
        "active": source.active,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None,
    }


@router.get("/sources/{source_id}/snapshots")
async def list_snapshots(
    source_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List recent snapshots for a source card."""
    # Verify source exists
    source_result = await db.execute(select(SourceCard).where(SourceCard.id == source_id))
    source = source_result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    query = (
        select(SourceSnapshot)
        .where(SourceSnapshot.source_card_id == source_id)
        .order_by(SourceSnapshot.fetched_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    snapshots = result.scalars().all()

    output = []
    for snap in snapshots:
        output.append(
            {
                "id": snap.id,
                "source_card_id": snap.source_card_id,
                "snapshot_hash": snap.snapshot_hash,
                "snapshot_path": snap.snapshot_path,
                "file_size_bytes": snap.file_size_bytes,
                "record_count": snap.record_count,
                "fetch_parameters": safe_json_loads(snap.fetch_parameters),
                "fetched_at": snap.fetched_at.isoformat() if snap.fetched_at else None,
                "verified_at": snap.verified_at.isoformat() if snap.verified_at else None,
            }
        )

    return {"source_id": source_id, "snapshots": output, "total": len(output)}
