"""API routes for per-paper autonomy cards."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.autonomy_card import AutonomyCard
from app.services.paper_generation.autonomy_tracker import get_family_autonomy_stats
from app.utils import safe_json_loads

router = APIRouter()


@router.get("/papers/{paper_id}/autonomy-card")
async def get_autonomy_card(paper_id: str, db: AsyncSession = Depends(get_db)):
    """Get the autonomy card for a paper."""
    result = await db.execute(select(AutonomyCard).where(AutonomyCard.paper_id == paper_id))
    card = result.scalar_one_or_none()

    if card is None:
        return {"paper_id": paper_id, "card": None}

    return {
        "paper_id": paper_id,
        "card": {
            "role_autonomy": safe_json_loads(card.role_autonomy_json, {}),
            "human_intervention_points": safe_json_loads(card.human_intervention_points_json, []),
            "overall_autonomy_score": card.overall_autonomy_score,
            "created_at": card.created_at.isoformat() if card.created_at else None,
            "updated_at": card.updated_at.isoformat() if card.updated_at else None,
        },
    }


@router.get("/families/{family_id}/autonomy-stats")
async def get_autonomy_stats(family_id: str, db: AsyncSession = Depends(get_db)):
    """Get aggregate autonomy stats for a paper family."""
    stats = await get_family_autonomy_stats(db, family_id)
    return {"family_id": family_id, **stats}
