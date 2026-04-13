"""Tracks per-role autonomy levels for each paper."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.autonomy_card import AutonomyCard
from app.models.paper import Paper
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

PIPELINE_ROLES = ["scout", "designer", "data_steward", "analyst", "drafter", "verifier", "packager"]
AUTONOMY_LEVELS = {"full_auto", "supervised", "human_driven"}


async def record_role_autonomy(
    session: AsyncSession,
    paper_id: str,
    role: str,
    level: str = "full_auto",
    description: str | None = None,
) -> AutonomyCard:
    """Record or update the autonomy level for a specific pipeline role.

    Creates the AutonomyCard if it doesn't exist yet.
    """
    if level not in AUTONOMY_LEVELS:
        level = "full_auto"

    result = await session.execute(
        select(AutonomyCard).where(AutonomyCard.paper_id == paper_id)
    )
    card = result.scalar_one_or_none()

    if card is None:
        # Initialize with all roles as "full_auto"
        role_autonomy = {r: "full_auto" for r in PIPELINE_ROLES}
        role_autonomy[role] = level
        card = AutonomyCard(
            paper_id=paper_id,
            role_autonomy_json=json.dumps(role_autonomy),
            human_intervention_points_json=json.dumps([]),
            overall_autonomy_score=_compute_score(role_autonomy),
        )
        session.add(card)
    else:
        role_autonomy = safe_json_loads(card.role_autonomy_json, {})
        role_autonomy[role] = level
        card.role_autonomy_json = json.dumps(role_autonomy)
        card.overall_autonomy_score = _compute_score(role_autonomy)

    # Record intervention point if not full_auto
    if level != "full_auto" and description:
        interventions = safe_json_loads(card.human_intervention_points_json, [])
        interventions.append({
            "role": role,
            "level": level,
            "description": description,
        })
        card.human_intervention_points_json = json.dumps(interventions)

    await session.flush()
    logger.info(
        "Autonomy for paper %s, role %s: %s (overall: %.2f)",
        paper_id, role, level, card.overall_autonomy_score,
    )
    return card


def _compute_score(role_autonomy: dict) -> float:
    """Compute overall autonomy score (fraction of roles that are full_auto)."""
    if not role_autonomy:
        return 0.0
    full_auto_count = sum(1 for v in role_autonomy.values() if v == "full_auto")
    return round(full_auto_count / len(role_autonomy), 2)


async def get_family_autonomy_stats(
    session: AsyncSession, family_id: str
) -> dict:
    """Aggregate autonomy stats across papers in a family."""
    result = await session.execute(
        select(AutonomyCard)
        .join(Paper, AutonomyCard.paper_id == Paper.id)
        .where(Paper.family_id == family_id)
    )
    cards = result.scalars().all()

    if not cards:
        return {"total_papers": 0, "avg_autonomy_score": 0.0, "role_breakdown": {}}

    scores = [c.overall_autonomy_score for c in cards]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    # Aggregate per-role autonomy distribution
    role_breakdown: dict[str, dict[str, int]] = {r: {"full_auto": 0, "supervised": 0, "human_driven": 0} for r in PIPELINE_ROLES}
    for card in cards:
        ra = safe_json_loads(card.role_autonomy_json, {})
        for role, level in ra.items():
            if role in role_breakdown and level in role_breakdown[role]:
                role_breakdown[role][level] += 1

    return {
        "total_papers": len(cards),
        "avg_autonomy_score": round(avg_score, 2),
        "role_breakdown": role_breakdown,
    }
