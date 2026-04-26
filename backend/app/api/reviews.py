import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.models.paper import Paper
from app.models.review import Review
from app.services.review_pipeline.orchestrator import run_review_pipeline

limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/papers/{paper_id}/reviews")
async def get_reviews(paper_id: str, db: AsyncSession = Depends(get_db)):
    paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    reviews = (
        await db.execute(
            select(Review)
            .where(Review.paper_id == paper_id)
            .order_by(Review.stage, Review.iteration)
        )
    ).scalars().all()

    return [
        {
            "id": r.id,
            "stage": r.stage,
            "model_used": r.model_used,
            "verdict": r.verdict,
            "content": r.content,
            "iteration": r.iteration,
            "created_at": r.created_at,
        }
        for r in reviews
    ]


@router.post("/papers/{paper_id}/review")
@limiter.limit("10/hour")
async def trigger_review(
    request: Request,
    paper_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    background_tasks.add_task(_run_review_background, paper_id)

    return {"paper_id": paper_id, "status": "review_started"}


async def _run_review_background(paper_id: str) -> None:
    """Background task wrapper: creates its own DB session and handles errors."""
    async with async_session() as session:
        try:
            await run_review_pipeline(session, paper_id)
        except Exception:
            await session.rollback()
            logger.exception("Review pipeline failed for paper %s", paper_id)
