from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.match import Match
from app.models.paper import Paper
from app.schemas.match import MatchDetail, MatchResponse

router = APIRouter()


@router.get("/matches", response_model=list[MatchResponse])
async def list_matches(
    tournament_run_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=250),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Match).order_by(Match.created_at.desc())

    if tournament_run_id:
        query = query.where(Match.tournament_run_id == tournament_run_id)

    query = query.offset(offset).limit(limit)
    results = (await db.execute(query)).scalars().all()
    return [MatchResponse.model_validate(m) for m in results]


@router.get("/matches/{match_id}", response_model=MatchDetail)
async def get_match(match_id: int, db: AsyncSession = Depends(get_db)):
    match = (await db.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Fetch both titles in a single query
    titles_result = await db.execute(
        select(Paper.id, Paper.title).where(Paper.id.in_([match.paper_a_id, match.paper_b_id]))
    )
    titles = {row.id: row.title for row in titles_result}

    detail = MatchDetail.model_validate(match)
    detail.paper_a_title = titles.get(match.paper_a_id)
    detail.paper_b_title = titles.get(match.paper_b_id)
    return detail
