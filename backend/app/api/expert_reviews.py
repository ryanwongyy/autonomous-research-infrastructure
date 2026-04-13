"""API routes for external expert reviews."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.expert_review import ExpertReview

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)


class CreateExpertReviewRequest(BaseModel):
    expert_name: str = Field(..., max_length=200)
    affiliation: str | None = Field(None, max_length=500)
    review_date: str = Field(..., max_length=50)
    overall_score: int = Field(..., ge=1, le=5)
    methodology_score: int | None = Field(None, ge=1, le=5)
    contribution_score: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=50000)
    is_pre_submission: bool = True


@router.post("/papers/{paper_id}/expert-reviews")
@limiter.limit("30/hour")
async def create_expert_review(
    request: Request,
    paper_id: str,
    body: CreateExpertReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record an external expert review."""
    try:
        review_date = datetime.fromisoformat(body.review_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid review_date format; use ISO 8601")

    review = ExpertReview(
        paper_id=paper_id,
        expert_name=body.expert_name,
        affiliation=body.affiliation,
        review_date=review_date,
        overall_score=body.overall_score,
        methodology_score=body.methodology_score,
        contribution_score=body.contribution_score,
        notes=body.notes,
        is_pre_submission=body.is_pre_submission,
    )
    db.add(review)
    try:
        await db.commit()
        await db.refresh(review)
    except Exception:
        await db.rollback()
        logger.exception("Failed to create expert review for paper %s", paper_id)
        raise HTTPException(status_code=500, detail="Failed to create expert review")

    return {
        "id": review.id,
        "paper_id": paper_id,
        "expert_name": review.expert_name,
        "overall_score": review.overall_score,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


@router.get("/papers/{paper_id}/expert-reviews")
async def get_paper_expert_reviews(paper_id: str, db: AsyncSession = Depends(get_db)):
    """List all expert reviews for a paper."""
    result = await db.execute(
        select(ExpertReview)
        .where(ExpertReview.paper_id == paper_id)
        .order_by(ExpertReview.review_date.desc())
    )
    reviews = result.scalars().all()
    return [
        {
            "id": r.id,
            "expert_name": r.expert_name,
            "affiliation": r.affiliation,
            "review_date": r.review_date.isoformat() if r.review_date else None,
            "overall_score": r.overall_score,
            "methodology_score": r.methodology_score,
            "contribution_score": r.contribution_score,
            "notes": r.notes,
            "is_pre_submission": r.is_pre_submission,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reviews
    ]
