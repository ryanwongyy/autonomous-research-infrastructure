"""API routes for novelty detection."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.novelty_check import NoveltyCheck
from app.services.novelty.detector import check_novelty
from app.utils import safe_json_loads

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/papers/{paper_id}/novelty-check")
@limiter.limit("10/hour")
async def trigger_novelty_check(
    request: Request, paper_id: str, db: AsyncSession = Depends(get_db)
):
    """Trigger a novelty check for a paper."""
    try:
        check = await check_novelty(db, paper_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Novelty check failed for paper %s", paper_id)
        raise HTTPException(status_code=500, detail="Novelty check failed")

    return {
        "id": check.id,
        "paper_id": paper_id,
        "verdict": check.verdict,
        "highest_similarity_score": check.highest_similarity_score,
        "checked_against_count": check.checked_against_count,
        "similar_papers": safe_json_loads(check.similar_paper_ids_json, []),
        "model_used": check.model_used,
        "created_at": check.created_at.isoformat() if check.created_at else None,
    }


@router.get("/papers/{paper_id}/novelty-check")
async def get_novelty_check(paper_id: str, db: AsyncSession = Depends(get_db)):
    """Get the most recent novelty check for a paper."""
    result = await db.execute(
        select(NoveltyCheck)
        .where(NoveltyCheck.paper_id == paper_id)
        .order_by(NoveltyCheck.created_at.desc())
        .limit(1)
    )
    check = result.scalar_one_or_none()

    if check is None:
        return {"paper_id": paper_id, "check": None}

    return {
        "paper_id": paper_id,
        "check": {
            "id": check.id,
            "verdict": check.verdict,
            "highest_similarity_score": check.highest_similarity_score,
            "checked_against_count": check.checked_against_count,
            "similar_papers": safe_json_loads(check.similar_paper_ids_json, []),
            "model_used": check.model_used,
            "created_at": check.created_at.isoformat() if check.created_at else None,
        },
    }
