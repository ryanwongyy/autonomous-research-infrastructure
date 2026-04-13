"""API routes for significance memos."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.release.significance_memo_service import (
    create_memo,
    get_memo_for_paper,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateMemoRequest(BaseModel):
    author: str = Field(..., max_length=200)
    memo_text: str = Field(..., max_length=50000)
    editorial_verdict: Literal["submit", "hold", "kill"]


@router.get("/papers/{paper_id}/significance-memo")
async def get_significance_memo(paper_id: str, db: AsyncSession = Depends(get_db)):
    """Get the most recent significance memo for a paper."""
    memo = await get_memo_for_paper(db, paper_id)
    if memo is None:
        return {"paper_id": paper_id, "memo": None}

    return {
        "paper_id": paper_id,
        "memo": {
            "id": memo.id,
            "author": memo.author,
            "memo_text": memo.memo_text,
            "tournament_rank_at_time": memo.tournament_rank_at_time,
            "tournament_confidence_json": memo.tournament_confidence_json,
            "editorial_verdict": memo.editorial_verdict,
            "created_at": memo.created_at.isoformat() if memo.created_at else None,
        },
    }


@router.post("/papers/{paper_id}/significance-memo")
async def create_significance_memo(
    paper_id: str,
    body: CreateMemoRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a significance memo for a paper."""
    try:
        memo = await create_memo(
            db,
            paper_id=paper_id,
            author=body.author,
            memo_text=body.memo_text,
            editorial_verdict=body.editorial_verdict,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to create significance memo for paper %s", paper_id)
        raise HTTPException(status_code=500, detail="Failed to create significance memo")

    return {
        "id": memo.id,
        "paper_id": paper_id,
        "author": memo.author,
        "editorial_verdict": memo.editorial_verdict,
        "created_at": memo.created_at.isoformat() if memo.created_at else None,
    }
