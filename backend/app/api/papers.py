import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import admin_key_required
from app.database import get_db
from app.models.paper import Paper
from app.models.rating import Rating
from app.schemas.paper import PaperCreate, PaperImport, PaperResponse, PaperWithRating
from app.config import settings

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)


def generate_paper_id() -> str:
    count = uuid.uuid4().hex[:8]
    return f"apep_{count}"


@router.get("/papers", response_model=list[PaperWithRating])
async def list_papers(
    source: str | None = Query(None, max_length=64),
    category: str | None = Query(None, max_length=64),
    country: str | None = Query(None, max_length=64),
    status: str | None = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=250),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Paper).outerjoin(Rating, Paper.id == Rating.paper_id)

    if source:
        query = query.where(Paper.source == source)
    if category:
        query = query.where(Paper.category == category)
    if country:
        query = query.where(Paper.country == country)
    if status:
        query = query.where(Paper.status == status)

    query = query.order_by(Paper.created_at.desc()).offset(offset).limit(limit)
    results = (await db.execute(query)).scalars().unique().all()

    papers = []
    for paper in results:
        data = PaperWithRating.model_validate(paper)
        if paper.rating:
            data.mu = paper.rating.mu
            data.sigma = paper.rating.sigma
            data.conservative_rating = paper.rating.conservative_rating
            data.elo = paper.rating.elo
            data.matches_played = paper.rating.matches_played
            data.rank = paper.rating.rank
            data.rank_change_48h = paper.rating.rank_change_48h
        papers.append(data)

    return papers


@router.get("/papers/{paper_id}", response_model=PaperWithRating)
async def get_paper(paper_id: str, db: AsyncSession = Depends(get_db)):
    paper = (
        await db.execute(
            select(Paper).where(Paper.id == paper_id)
        )
    ).scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    data = PaperWithRating.model_validate(paper)
    if paper.rating:
        data.mu = paper.rating.mu
        data.sigma = paper.rating.sigma
        data.conservative_rating = paper.rating.conservative_rating
        data.elo = paper.rating.elo
        data.matches_played = paper.rating.matches_played
        data.rank = paper.rating.rank
        data.rank_change_48h = paper.rating.rank_change_48h

    return data


@router.get("/papers/{paper_id}/export")
async def export_paper(
    paper_id: str,
    format: str = Query("pdf", pattern="^(pdf|tex)$"),
    db: AsyncSession = Depends(get_db),
):
    """Download the compiled PDF or TeX source for a paper."""
    paper = (
        await db.execute(select(Paper).where(Paper.id == paper_id))
    ).scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if format == "pdf":
        path = paper.paper_pdf_path
        media_type = "application/pdf"
    else:
        path = paper.paper_tex_path
        media_type = "application/x-tex"

    if not path:
        raise HTTPException(
            status_code=404,
            detail=f"No {format.upper()} artifact available for this paper",
        )

    file_path = Path(path)
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"{format.upper()} file not found on disk",
        )

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"{paper_id}.{format}",
    )


@router.post("/papers", response_model=PaperResponse)
async def create_paper(paper_in: PaperCreate, db: AsyncSession = Depends(get_db)):
    paper_id = paper_in.id or generate_paper_id()

    paper = Paper(
        id=paper_id,
        title=paper_in.title,
        abstract=paper_in.abstract,
        source=paper_in.source,
        category=paper_in.category,
        country=paper_in.country,
        method=paper_in.method,
        version=paper_in.version,
        status="published",
        review_status="awaiting",
        domain_config_id=paper_in.domain_config_id,
    )
    db.add(paper)

    rating = Rating(
        paper_id=paper_id,
        mu=settings.trueskill_mu,
        sigma=settings.trueskill_sigma,
        conservative_rating=settings.trueskill_mu - 3 * settings.trueskill_sigma,
        elo=settings.elo_default,
    )
    db.add(rating)

    try:
        await db.commit()
        await db.refresh(paper)
    except Exception:
        await db.rollback()
        logger.exception("Failed to create paper")
        raise HTTPException(status_code=500, detail="Failed to create paper")
    return PaperResponse.model_validate(paper)


@router.post(
    "/papers/import",
    response_model=list[PaperResponse],
    dependencies=[Depends(admin_key_required)],
)
@limiter.limit("10/hour")
async def import_papers(request: Request, data: PaperImport, db: AsyncSession = Depends(get_db)):
    created = []
    # Pre-generate IDs and batch-check existence to avoid N+1
    candidate_ids = [p.id or generate_paper_id() for p in data.papers]
    existing_result = await db.execute(
        select(Paper.id).where(Paper.id.in_(candidate_ids))
    )
    existing_ids = set(existing_result.scalars().all())

    for paper_in, paper_id in zip(data.papers, candidate_ids):
        if paper_id in existing_ids:
            continue

        paper = Paper(
            id=paper_id,
            title=paper_in.title,
            abstract=paper_in.abstract,
            source=paper_in.source,
            category=paper_in.category,
            country=paper_in.country,
            method=paper_in.method,
            version=paper_in.version,
            status="published",
            review_status="peer_reviewed" if paper_in.source in ("aer", "aej_policy", "benchmark") else "awaiting",
            domain_config_id=paper_in.domain_config_id,
        )
        db.add(paper)

        rating = Rating(
            paper_id=paper_id,
            mu=settings.trueskill_mu,
            sigma=settings.trueskill_sigma,
            conservative_rating=settings.trueskill_mu - 3 * settings.trueskill_sigma,
            elo=settings.elo_default,
        )
        db.add(rating)
        created.append(paper)

    try:
        await db.commit()
        for p in created:
            await db.refresh(p)
    except Exception:
        await db.rollback()
        logger.exception("Failed to import papers (batch of %d)", len(data.papers))
        raise HTTPException(status_code=500, detail="Failed to import papers")

    return [PaperResponse.model_validate(p) for p in created]
