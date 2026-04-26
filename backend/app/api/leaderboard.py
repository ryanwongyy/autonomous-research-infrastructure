from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardResponse

router = APIRouter()


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    family_id: str = Query(
        ...,
        max_length=64,
        description="Required. Family ID to scope the leaderboard. No cross-family ranking is supported.",
    ),
    sort_by: str = Query(
        "conservative_rating",
        pattern="^(conservative_rating|mu|elo|matches_played)$",
    ),
    source: str | None = Query(None, max_length=64),
    category: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=250),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Return the leaderboard scoped to a single family.

    ``family_id`` is **required** -- cross-family ranking is not supported.
    Returns 404 if the family does not exist.
    """
    # Validate family exists
    family = (
        await db.execute(
            select(PaperFamily).where(PaperFamily.id == family_id)
        )
    ).scalar_one_or_none()

    if not family:
        raise HTTPException(
            status_code=404,
            detail=f"Family '{family_id}' not found. A family_id is required for leaderboard queries.",
        )

    query = (
        select(Paper, Rating)
        .join(Rating, Paper.id == Rating.paper_id)
        .where(Paper.status == "published")
        .where(Paper.family_id == family_id)
    )

    if source:
        query = query.where(Paper.source == source)
    if category:
        query = query.where(Paper.category == category)

    allowed_sorts = {
        "conservative_rating": Rating.conservative_rating,
        "mu": Rating.mu,
        "elo": Rating.elo,
        "matches_played": Rating.matches_played,
    }
    sort_col = allowed_sorts.get(sort_by)
    if sort_col is None:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    query = query.order_by(sort_col.desc())

    count_query = (
        select(func.count())
        .select_from(Paper)
        .join(Rating, Paper.id == Rating.paper_id)
        .where(Paper.status == "published")
        .where(Paper.family_id == family_id)
    )
    if source:
        count_query = count_query.where(Paper.source == source)
    if category:
        count_query = count_query.where(Paper.category == category)
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset(offset).limit(limit)
    results = (await db.execute(query)).all()

    entries = []
    for paper, rating in results:
        entries.append(
            LeaderboardEntry(
                rank=rating.rank,
                rank_change_48h=rating.rank_change_48h,
                paper_id=paper.id,
                title=paper.title,
                source=paper.source,
                category=paper.category,
                mu=rating.mu,
                sigma=rating.sigma,
                conservative_rating=rating.conservative_rating,
                elo=rating.elo,
                matches_played=rating.matches_played,
                wins=rating.wins,
                losses=rating.losses,
                draws=rating.draws,
                review_status=paper.review_status,
            )
        )

    return LeaderboardResponse(
        entries=entries,
        total=total,
        offset=offset,
        limit=limit,
        family_id=family_id,
        family_name=family.name,
    )
