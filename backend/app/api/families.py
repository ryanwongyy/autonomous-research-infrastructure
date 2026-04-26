from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.utils import safe_json_loads

router = APIRouter()


@router.get("/families")
async def list_families(active_only: bool = True, db: AsyncSession = Depends(get_db)):
    """List all paper families with paper counts."""
    query = select(PaperFamily)
    if active_only:
        query = query.where(PaperFamily.active.is_(True))
    query = query.order_by(PaperFamily.id)
    result = await db.execute(query)
    families = result.scalars().all()

    # Get all paper counts in a single GROUP BY query (avoids N+1)
    count_q = (
        select(Paper.family_id, func.count())
        .group_by(Paper.family_id)
    )
    count_result = await db.execute(count_q)
    paper_counts = dict(count_result.all())

    output = []
    for fam in families:
        paper_count = paper_counts.get(fam.id, 0)

        output.append({
            "id": fam.id,
            "name": fam.name,
            "short_name": fam.short_name,
            "description": fam.description,
            "lock_protocol_type": fam.lock_protocol_type,
            "venue_ladder": safe_json_loads(fam.venue_ladder),
            "mandatory_checks": safe_json_loads(fam.mandatory_checks, []),
            "fatal_failures": safe_json_loads(fam.fatal_failures, []),
            "elite_ceiling": fam.elite_ceiling,
            "max_portfolio_share": fam.max_portfolio_share,
            "paper_count": paper_count,
            "active": fam.active,
        })

    return {"families": output, "total": len(output)}


@router.get("/families/{family_id}")
async def get_family(family_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed info for a single family."""
    result = await db.execute(select(PaperFamily).where(PaperFamily.id == family_id))
    family = result.scalar_one_or_none()
    if not family:
        raise HTTPException(status_code=404, detail=f"Family {family_id} not found")

    # Get paper counts by funnel stage
    stages_q = (
        select(Paper.funnel_stage, func.count())
        .where(Paper.family_id == family_id)
        .group_by(Paper.funnel_stage)
    )
    stages_result = await db.execute(stages_q)
    funnel = {row[0]: row[1] for row in stages_result}

    return {
        "id": family.id,
        "name": family.name,
        "short_name": family.short_name,
        "description": family.description,
        "lock_protocol_type": family.lock_protocol_type,
        "canonical_questions": safe_json_loads(family.canonical_questions, []),
        "accepted_methods": safe_json_loads(family.accepted_methods, []),
        "public_data_sources": safe_json_loads(family.public_data_sources, []),
        "novelty_threshold": family.novelty_threshold,
        "venue_ladder": safe_json_loads(family.venue_ladder),
        "mandatory_checks": safe_json_loads(family.mandatory_checks, []),
        "fatal_failures": safe_json_loads(family.fatal_failures, []),
        "elite_ceiling": family.elite_ceiling,
        "benchmark_config": safe_json_loads(family.benchmark_config),
        "review_rubric": safe_json_loads(family.review_rubric),
        "max_portfolio_share": family.max_portfolio_share,
        "funnel_stages": funnel,
        "active": family.active,
    }
