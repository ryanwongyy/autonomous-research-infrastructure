"""API routes for cohort-adjusted metrics."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.cohort_tag import CohortTag
from app.services.cohort.cohort_service import (
    get_cohort_comparison,
)

router = APIRouter()


@router.get("/cohorts")
async def list_cohorts(db: AsyncSession = Depends(get_db)):
    """List all cohorts with summary stats."""
    comparison = await get_cohort_comparison(db)
    return comparison


@router.get("/cohorts/{cohort_id}")
async def get_cohort(cohort_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed metrics for a specific cohort."""
    comparison = await get_cohort_comparison(db, cohort_id=cohort_id)
    cohorts = comparison.get("cohorts", [])
    if not cohorts:
        return {"cohort_id": cohort_id, "metrics": None}
    return {"cohort_id": cohort_id, "metrics": cohorts[0]}


@router.get("/papers/{paper_id}/cohort")
async def get_paper_cohort(paper_id: str, db: AsyncSession = Depends(get_db)):
    """Get which cohort a paper belongs to."""
    result = await db.execute(select(CohortTag).where(CohortTag.paper_id == paper_id))
    tag = result.scalar_one_or_none()

    if tag is None:
        return {"paper_id": paper_id, "cohort": None}

    return {
        "paper_id": paper_id,
        "cohort": {
            "cohort_id": tag.cohort_id,
            "generation_model": tag.generation_model,
            "review_models_json": tag.review_models_json,
            "tournament_judge_model": tag.tournament_judge_model,
            "created_at": tag.created_at.isoformat() if tag.created_at else None,
        },
    }
