"""API routes for submission outcomes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.submission_outcome import SubmissionOutcome
from app.services.outcomes.outcome_tracker import (
    get_outcomes_dashboard,
    record_outcome,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateOutcomeRequest(BaseModel):
    venue_name: str = Field(..., max_length=300)
    submitted_date: str = Field(..., max_length=50)
    decision: str | None = Field(None, max_length=100)
    decision_date: str | None = Field(None, max_length=50)
    revision_rounds: int = Field(0, ge=0, le=20)
    reviewer_feedback_summary: str | None = Field(None, max_length=50000)


@router.post("/papers/{paper_id}/outcomes")
async def create_outcome(
    paper_id: str,
    body: CreateOutcomeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a submission outcome."""
    try:
        outcome = await record_outcome(
            db,
            paper_id=paper_id,
            venue_name=body.venue_name,
            submitted_date=body.submitted_date,
            decision=body.decision,
            decision_date=body.decision_date,
            revision_rounds=body.revision_rounds,
            reviewer_feedback_summary=body.reviewer_feedback_summary,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to record outcome for paper %s", paper_id)
        raise HTTPException(status_code=500, detail="Failed to record outcome")

    return {
        "id": outcome.id,
        "paper_id": paper_id,
        "venue_name": outcome.venue_name,
        "decision": outcome.decision,
    }


@router.get("/papers/{paper_id}/outcomes")
async def get_paper_outcomes(paper_id: str, db: AsyncSession = Depends(get_db)):
    """List all submission outcomes for a paper."""
    result = await db.execute(
        select(SubmissionOutcome)
        .where(SubmissionOutcome.paper_id == paper_id)
        .order_by(SubmissionOutcome.submitted_date.desc())
    )
    outcomes = result.scalars().all()
    return [
        {
            "id": o.id,
            "venue_name": o.venue_name,
            "submitted_date": o.submitted_date.isoformat() if o.submitted_date else None,
            "decision": o.decision,
            "decision_date": o.decision_date.isoformat() if o.decision_date else None,
            "revision_rounds": o.revision_rounds,
            "reviewer_feedback_summary": o.reviewer_feedback_summary,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in outcomes
    ]


@router.get("/outcomes/dashboard")
async def outcomes_dashboard(db: AsyncSession = Depends(get_db)):
    """Get aggregated outcomes dashboard data."""
    return await get_outcomes_dashboard(db)
