from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.paper import Paper
from app.services.release.release_manager import (
    check_transition_preconditions,
    get_release_pipeline_status,
    transition_release_status,
)

router = APIRouter()


@router.get("/release/status")
async def get_release_overview(
    family_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get overview of papers in each release stage."""
    result = await get_release_pipeline_status(db, family_id=family_id)
    return result


@router.get("/papers/{paper_id}/release")
async def get_paper_release_status(
    paper_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get release status for a specific paper."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

    return {
        "paper_id": paper.id,
        "title": paper.title,
        "release_status": paper.release_status,
        "funnel_stage": paper.funnel_stage,
        "family_id": paper.family_id,
        "lock_hash": paper.lock_hash,
        "updated_at": paper.updated_at.isoformat() if paper.updated_at else None,
    }


@router.post("/papers/{paper_id}/release/transition")
async def transition_paper(
    paper_id: str,
    target_status: Literal["internal", "candidate", "submitted", "public"] = Query(...),
    force: bool = False,
    approved_by: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Transition a paper's release status.

    Query params:
    - target_status: the desired release status (candidate, submitted, public, internal)
    - force: if true, override unmet preconditions (requires admin key + approved_by)
    - approved_by: identifier of the approver (required for force and some transitions)
    """
    if force and not approved_by:
        raise HTTPException(
            status_code=400,
            detail="Force transitions require approved_by to be set for audit trail",
        )
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

    transition_result = await transition_release_status(
        db,
        paper_id=paper_id,
        target_status=target_status,
        force=force,
        approved_by=approved_by,
    )

    if not transition_result["success"]:
        raise HTTPException(
            status_code=409,
            detail=transition_result,
        )

    return transition_result


@router.get("/papers/{paper_id}/release/preconditions")
async def check_preconditions(
    paper_id: str,
    target_status: Literal["internal", "candidate", "submitted", "public"] = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Check preconditions for a release transition.

    Query params:
    - target_status: the desired release status to check against
    """
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

    check = await check_transition_preconditions(db, paper_id, target_status)
    return check
