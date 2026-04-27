"""API routes for reliability metrics."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.reliability.reliability_engine import (
    compute_family_reliability,
    compute_paper_reliability,
    get_reliability_overview,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/reliability/paper/{paper_id}")
async def get_paper_reliability(paper_id: str, db: AsyncSession = Depends(get_db)):
    """Compute and return reliability metrics for a single paper."""
    try:
        metrics = await compute_paper_reliability(db, paper_id)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to compute paper reliability for %s", paper_id)
        raise HTTPException(status_code=500, detail="Failed to compute paper reliability")
    return {"paper_id": paper_id, "metrics": metrics}


@router.get("/reliability/family/{family_id}")
async def get_family_reliability(family_id: str, db: AsyncSession = Depends(get_db)):
    """Get aggregated reliability metrics for a paper family."""
    metrics = await compute_family_reliability(db, family_id)
    return {"family_id": family_id, "metrics": metrics}


@router.get("/reliability/overview")
async def reliability_overview(db: AsyncSession = Depends(get_db)):
    """System-wide reliability dashboard data."""
    overview = await get_reliability_overview(db)
    return overview
