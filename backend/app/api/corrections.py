"""API routes for correction records."""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.correction_record import CorrectionRecord
from app.models.paper import Paper
from app.models.paper_family import PaperFamily

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)


class CreateCorrectionRequest(BaseModel):
    correction_type: Literal["erratum", "retraction", "update"]
    description: str = Field(..., max_length=50000)
    affected_claims_json: str | None = Field(None, max_length=50000)
    corrected_at: str = Field(..., max_length=50)
    published_at: str | None = Field(None, max_length=50)


@router.post("/papers/{paper_id}/corrections")
@limiter.limit("30/hour")
async def create_correction(
    request: Request,
    paper_id: str,
    body: CreateCorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a correction for a paper."""
    try:
        corrected_at = datetime.fromisoformat(body.corrected_at)
        published_at = datetime.fromisoformat(body.published_at) if body.published_at else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format; use ISO 8601")

    record = CorrectionRecord(
        paper_id=paper_id,
        correction_type=body.correction_type,
        description=body.description,
        affected_claims_json=body.affected_claims_json,
        corrected_at=corrected_at,
        published_at=published_at,
    )
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
    except Exception:
        await db.rollback()
        logger.exception("Failed to create correction record for paper %s", paper_id)
        raise HTTPException(status_code=500, detail="Failed to create correction record")

    return {
        "id": record.id,
        "paper_id": paper_id,
        "correction_type": record.correction_type,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.get("/papers/{paper_id}/corrections")
async def get_paper_corrections(paper_id: str, db: AsyncSession = Depends(get_db)):
    """List all corrections for a paper."""
    result = await db.execute(
        select(CorrectionRecord)
        .where(CorrectionRecord.paper_id == paper_id)
        .order_by(CorrectionRecord.corrected_at.desc())
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "correction_type": r.correction_type,
            "description": r.description,
            "affected_claims_json": r.affected_claims_json,
            "corrected_at": r.corrected_at.isoformat() if r.corrected_at else None,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.get("/corrections/dashboard")
async def corrections_dashboard(db: AsyncSession = Depends(get_db)):
    """Get correction rates by family."""
    families = (await db.execute(
        select(PaperFamily).where(PaperFamily.active.is_(True))
    )).scalars().all()
    family_map = {f.id: f.short_name for f in families}

    # Batch: public paper counts per family (1 query instead of N)
    paper_counts = dict(
        (await db.execute(
            select(Paper.family_id, func.count())
            .where(Paper.family_id.in_(family_map.keys()), Paper.release_status == "public")
            .group_by(Paper.family_id)
        )).all()
    )

    # Batch: correction counts per family (1 query instead of N)
    correction_counts = dict(
        (await db.execute(
            select(Paper.family_id, func.count())
            .select_from(CorrectionRecord)
            .join(Paper, CorrectionRecord.paper_id == Paper.id)
            .where(Paper.family_id.in_(family_map.keys()))
            .group_by(Paper.family_id)
        )).all()
    )

    result = []
    for fid, short_name in family_map.items():
        total = paper_counts.get(fid, 0)
        if total > 0:
            corr = correction_counts.get(fid, 0)
            result.append({
                "family_id": fid,
                "short_name": short_name,
                "total_public_papers": total,
                "total_corrections": corr,
                "correction_rate": round(corr / total, 4),
            })

    return {"families": result}
