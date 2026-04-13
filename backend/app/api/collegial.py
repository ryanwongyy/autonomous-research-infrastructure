"""API routes for the Collegial Review Loop.

Exposes endpoints for managing colleague profiles, triggering collegial
reviews on papers, and retrieving session/acknowledgment records.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.acknowledgment_record import AcknowledgmentRecord
from app.models.colleague_profile import ColleagueProfile
from app.services.collegial.review_loop import (
    ensure_default_colleagues,
    get_colleague_profiles,
    get_session_for_paper,
    run_full_collegial_review,
)

limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ColleagueProfileCreate(BaseModel):
    name: str = Field(..., max_length=200)
    expertise_area: str = Field(..., max_length=500)
    perspective_description: str = Field(..., max_length=5000)
    system_prompt: str = Field(..., max_length=50000)


class CollegialReviewBody(BaseModel):
    manuscript_latex: Optional[str] = Field(None, max_length=500000)
    target_venue: Optional[str] = Field(None, max_length=300)
    max_rounds: int = Field(5, ge=1, le=20)


# ---------------------------------------------------------------------------
# GET /collegial/profiles — list all colleague profiles
# ---------------------------------------------------------------------------

@router.get("/collegial/profiles")
async def list_profiles(db: AsyncSession = Depends(get_db)):
    """Return all colleague profiles."""

    # Ensure defaults exist on first call
    await ensure_default_colleagues(db)

    profiles = await get_colleague_profiles(db)
    return {"profiles": profiles}


# ---------------------------------------------------------------------------
# GET /papers/{paper_id}/collegial-session — latest collegial session
# ---------------------------------------------------------------------------

@router.get("/papers/{paper_id}/collegial-session")
async def get_collegial_session(
    paper_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return the latest collegial review session for a paper."""
    session_data = await get_session_for_paper(db, paper_id)
    if session_data is None:
        return {"session": None}
    return {"session": session_data}


# ---------------------------------------------------------------------------
# GET /papers/{paper_id}/acknowledgments — acknowledgment records
# ---------------------------------------------------------------------------

@router.get("/papers/{paper_id}/acknowledgments")
async def get_acknowledgments(
    paper_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return all acknowledgment records for a paper."""
    result = await db.execute(
        select(AcknowledgmentRecord).where(
            AcknowledgmentRecord.paper_id == paper_id
        )
    )
    records = result.scalars().all()
    return {
        "acknowledgments": [
            {
                "id": r.id,
                "paper_id": r.paper_id,
                "colleague_id": r.colleague_id,
                "contribution_type": r.contribution_type,
                "contribution_summary": r.contribution_summary,
                "exchanges_count": r.exchanges_count,
                "accepted_suggestions": r.accepted_suggestions,
                "acknowledgment_text": r.acknowledgment_text,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
    }


# ---------------------------------------------------------------------------
# POST /papers/{paper_id}/collegial-review — trigger full collegial review
# ---------------------------------------------------------------------------

@router.post("/papers/{paper_id}/collegial-review")
@limiter.limit("5/hour")
async def trigger_collegial_review(
    request: Request,
    paper_id: str,
    body: CollegialReviewBody,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a full collegial review for a paper.

    If ``manuscript_latex`` is not provided in the body, the service will
    attempt to load it from the paper's existing draft.
    """
    try:
        result = await run_full_collegial_review(
            session=db,
            paper_id=paper_id,
            manuscript_latex=body.manuscript_latex,
            target_venue=body.target_venue,
            max_rounds=body.max_rounds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError:
        logger.exception("Collegial review runtime error for paper %s", paper_id)
        raise HTTPException(status_code=500, detail="Collegial review failed")
    except Exception:
        logger.exception("Unexpected error during collegial review for paper %s", paper_id)
        raise HTTPException(status_code=500, detail="Unexpected error during collegial review")

    return result


# ---------------------------------------------------------------------------
# POST /collegial/profiles — create a new colleague profile
# ---------------------------------------------------------------------------

@router.post("/collegial/profiles", status_code=201)
@limiter.limit("30/hour")
async def create_profile(
    request: Request,
    body: ColleagueProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new colleague profile."""
    profile = ColleagueProfile(
        name=body.name,
        expertise_area=body.expertise_area,
        perspective_description=body.perspective_description,
        system_prompt=body.system_prompt,
        active=True,
    )
    db.add(profile)
    try:
        await db.flush()
        await db.commit()
        await db.refresh(profile)
    except Exception:
        await db.rollback()
        logger.exception("Failed to create colleague profile")
        raise HTTPException(status_code=500, detail="Failed to create colleague profile")

    return {
        "id": profile.id,
        "name": profile.name,
        "expertise_area": profile.expertise_area,
        "perspective_description": profile.perspective_description,
        "active": profile.active,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    }
