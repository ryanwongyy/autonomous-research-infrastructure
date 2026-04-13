"""API routes for failure taxonomy."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.failure_record import FailureRecord
from app.services.failure_taxonomy.classifier import (
    get_failure_distribution,
    get_failure_trends,
)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)

FailureType = Literal[
    "data_error", "logic_error", "hallucination", "causal_overreach",
    "source_drift", "design_violation", "formatting", "other",
]
SeverityLevel = Literal["low", "medium", "high", "critical"]


class CreateFailureRequest(BaseModel):
    paper_id: str | None = Field(None, max_length=64)
    family_id: str | None = Field(None, max_length=64)
    failure_type: FailureType
    severity: SeverityLevel
    detection_stage: str = Field(..., max_length=200)
    root_cause_category: str | None = Field(None, max_length=200)
    resolution: str | None = Field(None, max_length=5000)
    corrective_action: str | None = Field(None, max_length=5000)


@router.post("/failures")
@limiter.limit("30/hour")
async def create_failure(request: Request, body: CreateFailureRequest, db: AsyncSession = Depends(get_db)):
    """Manually record a failure."""
    record = FailureRecord(
        paper_id=body.paper_id,
        family_id=body.family_id,
        failure_type=body.failure_type,
        severity=body.severity,
        detection_stage=body.detection_stage,
        root_cause_category=body.root_cause_category,
        resolution=body.resolution,
        corrective_action=body.corrective_action,
    )
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
    except Exception:
        await db.rollback()
        logger.exception("Failed to create failure record")
        raise HTTPException(status_code=500, detail="Failed to create failure record")

    return {
        "id": record.id,
        "failure_type": record.failure_type,
        "severity": record.severity,
        "detection_stage": record.detection_stage,
    }


@router.get("/failures/dashboard")
async def failures_dashboard(
    family_id: str | None = None,
    days: int = 90,
    db: AsyncSession = Depends(get_db),
):
    """Get failure distribution and trends."""
    distribution = await get_failure_distribution(db, family_id)
    trends = await get_failure_trends(db, days)
    return {"distribution": distribution, "trends": trends}


@router.get("/papers/{paper_id}/failures")
async def get_paper_failures(paper_id: str, db: AsyncSession = Depends(get_db)):
    """List all failures for a paper."""
    result = await db.execute(
        select(FailureRecord)
        .where(FailureRecord.paper_id == paper_id)
        .order_by(FailureRecord.created_at.desc())
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "failure_type": r.failure_type,
            "severity": r.severity,
            "detection_stage": r.detection_stage,
            "root_cause_category": r.root_cause_category,
            "resolution": r.resolution,
            "corrective_action": r.corrective_action,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
