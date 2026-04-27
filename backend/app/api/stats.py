from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, and_, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.match import Match
from app.models.paper import Paper
from app.models.rating import Rating
from app.models.rating_snapshot import RatingSnapshot
from app.models.tournament_run import TournamentRun
from app.schemas.stats import (
    RatingDistributionBucket,
    RatingDistributionResponse,
    StatsResponse,
    TrueSkillProgressionPoint,
    TrueSkillProgressionResponse,
)

router = APIRouter()

AI_SOURCES = {"ape"}
BENCHMARK_SOURCES = {"aer", "aej_policy", "benchmark"}


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Paper counts: total + AI in one query (was 2 queries)
    paper_row = (
        await db.execute(
            select(
                func.count(Paper.id).label("total"),
                func.sum(case((Paper.source.in_(AI_SOURCES), 1), else_=0)).label("total_ai"),
            )
        )
    ).one()
    total_papers = paper_row.total or 0
    total_ai = int(paper_row.total_ai or 0)
    total_benchmark = total_papers - total_ai

    # Match counts + AI wins in one query (was 2 queries)
    match_row = (
        await db.execute(
            select(
                func.count(Match.id).label("total"),
                func.sum(
                    case(
                        (and_(Match.winner_id.isnot(None), Match.winner_id == Match.paper_a_id), 1),
                        else_=0,
                    )
                ).label("ai_wins"),
            )
        )
    ).one()
    total_matches = match_row.total or 0
    ai_wins = int(match_row.ai_wins or 0)

    total_runs = (await db.execute(select(func.count(TournamentRun.id)))).scalar() or 0

    ai_win_rate = (ai_wins / total_matches) if total_matches > 0 else 0.0

    # Avg elo for both groups in one query (was 2 queries)
    elo_row = (
        await db.execute(
            select(
                func.avg(case((Paper.source.in_(AI_SOURCES), Rating.elo))).label("avg_ai"),
                func.avg(case((Paper.source.in_(BENCHMARK_SOURCES), Rating.elo))).label(
                    "avg_bench"
                ),
            ).join(Paper, Rating.paper_id == Paper.id)
        )
    ).one()

    return StatsResponse(
        total_papers=total_papers,
        total_ai_papers=total_ai,
        total_benchmark_papers=total_benchmark,
        total_matches=total_matches,
        total_tournament_runs=total_runs,
        ai_win_rate=round(ai_win_rate, 1),
        avg_elo_ai=round(elo_row.avg_ai, 1) if elo_row.avg_ai else None,
        avg_elo_benchmark=round(elo_row.avg_bench, 1) if elo_row.avg_bench else None,
    )


@router.get("/stats/rating-distribution", response_model=RatingDistributionResponse)
async def get_rating_distribution(
    bucket_size: float = Query(50.0, ge=5.0, le=1000.0),
    db: AsyncSession = Depends(get_db),
):
    is_ai = case((Paper.source.in_(AI_SOURCES), 1), else_=0)

    # Elo distribution — bucketed in SQL
    elo_bucket_start = cast(Rating.elo / bucket_size, Integer) * bucket_size
    elo_rows = (
        await db.execute(
            select(
                elo_bucket_start.label("bucket_start"),
                func.sum(is_ai).label("count_ai"),
                func.sum(1 - is_ai).label("count_benchmark"),
            )
            .select_from(Paper)
            .join(Rating, Paper.id == Rating.paper_id)
            .where(Paper.status == "published")
            .group_by(elo_bucket_start)
            .order_by(elo_bucket_start)
        )
    ).all()

    # Conservative distribution — bucketed in SQL
    cons_bucket_start = cast(Rating.conservative_rating / bucket_size, Integer) * bucket_size
    cons_rows = (
        await db.execute(
            select(
                cons_bucket_start.label("bucket_start"),
                func.sum(is_ai).label("count_ai"),
                func.sum(1 - is_ai).label("count_benchmark"),
            )
            .select_from(Paper)
            .join(Rating, Paper.id == Rating.paper_id)
            .where(Paper.status == "published")
            .group_by(cons_bucket_start)
            .order_by(cons_bucket_start)
        )
    ).all()

    return RatingDistributionResponse(
        elo_distribution=[
            RatingDistributionBucket(
                bucket_start=float(r.bucket_start),
                bucket_end=float(r.bucket_start) + bucket_size,
                count_ai=int(r.count_ai),
                count_benchmark=int(r.count_benchmark),
            )
            for r in elo_rows
        ],
        conservative_distribution=[
            RatingDistributionBucket(
                bucket_start=float(r.bucket_start),
                bucket_end=float(r.bucket_start) + bucket_size,
                count_ai=int(r.count_ai),
                count_benchmark=int(r.count_benchmark),
            )
            for r in cons_rows
        ],
    )


@router.get("/stats/trueskill-progression", response_model=TrueSkillProgressionResponse)
async def get_trueskill_progression(
    top_n: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Get top N papers by conservative rating
    top_papers = (
        await db.execute(
            select(Paper.id, Paper.title, Paper.source)
            .join(Rating, Paper.id == Rating.paper_id)
            .where(Paper.status == "published")
            .order_by(Rating.conservative_rating.desc())
            .limit(top_n)
        )
    ).all()

    paper_ids = [p.id for p in top_papers]
    paper_map = {p.id: (p.title, p.source) for p in top_papers}

    snapshots = (
        (
            await db.execute(
                select(RatingSnapshot)
                .where(RatingSnapshot.paper_id.in_(paper_ids))
                .order_by(RatingSnapshot.snapshot_date)
            )
        )
        .scalars()
        .all()
    )

    data = [
        TrueSkillProgressionPoint(
            date=str(s.snapshot_date),
            paper_id=s.paper_id,
            title=paper_map.get(s.paper_id, ("Unknown", "ape"))[0],
            source=paper_map.get(s.paper_id, ("Unknown", "ape"))[1],
            conservative_rating=s.conservative_rating,
        )
        for s in snapshots
    ]

    return TrueSkillProgressionResponse(data=data)
