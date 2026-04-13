from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.paper import Paper
from app.models.rating import Rating
from app.models.domain_config import DomainConfig
from app.schemas.leaderboard import LeaderboardEntry
from app.utils import safe_json_loads

router = APIRouter()


@router.get("/categories")
async def list_categories(
    domain_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # Get categories from domain configs
    query = select(DomainConfig).where(DomainConfig.active.is_(True))
    if domain_id:
        query = query.where(DomainConfig.id == domain_id)

    configs = (await db.execute(query)).scalars().all()

    # Collect all category slugs first, then get counts in a single query (avoids N+1)
    category_entries = []
    for config in configs:
        if not config.categories:
            continue
        cats = safe_json_loads(config.categories, [])
        for cat in cats:
            category_entries.append({"slug": cat["slug"], "name": cat["name"], "domain_id": config.id})

    if category_entries:
        all_slugs = [c["slug"] for c in category_entries]
        count_q = (
            select(Paper.category, func.count(Paper.id))
            .where(Paper.category.in_(all_slugs), Paper.status == "published")
            .group_by(Paper.category)
        )
        count_result = await db.execute(count_q)
        paper_counts = dict(count_result.all())
    else:
        paper_counts = {}

    categories = []
    for entry in category_entries:
        categories.append({
            **entry,
            "paper_count": paper_counts.get(entry["slug"], 0),
        })

    return categories


@router.get("/categories/{slug}")
async def get_category(
    slug: str,
    limit: int = Query(50, ge=1, le=250),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    results = (
        await db.execute(
            select(Paper, Rating)
            .join(Rating, Paper.id == Rating.paper_id)
            .where(Paper.category == slug, Paper.status == "published")
            .order_by(Rating.conservative_rating.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    if not results:
        raise HTTPException(status_code=404, detail="Category not found or empty")

    entries = [
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
        for paper, rating in results
    ]

    return {"slug": slug, "entries": entries, "total": len(entries)}
