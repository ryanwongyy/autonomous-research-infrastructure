from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.throughput.batch_scheduler import (
    compute_daily_targets,
    get_work_queue,
)
from app.services.throughput.funnel_tracker import (
    detect_bottlenecks,
    get_conversion_rates,
    get_funnel_snapshot,
    project_annual_output,
)

router = APIRouter()


@router.get("/throughput/funnel")
async def get_funnel(
    family_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get funnel snapshot with stage counts."""
    return await get_funnel_snapshot(db, family_id=family_id)


@router.get("/throughput/conversion-rates")
async def get_conversions(
    family_id: str | None = None,
    days: int = 365,
    db: AsyncSession = Depends(get_db),
):
    """Get stage-to-stage conversion rates."""
    return await get_conversion_rates(db, family_id=family_id, days=days)


@router.get("/throughput/bottlenecks")
async def get_bottlenecks(
    family_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Detect pipeline bottlenecks."""
    return await detect_bottlenecks(db, family_id=family_id)


@router.get("/throughput/projections")
async def get_projections(
    db: AsyncSession = Depends(get_db),
):
    """Project annual output vs targets."""
    return await project_annual_output(db)


@router.get("/throughput/daily-targets")
async def get_daily_targets(
    db: AsyncSession = Depends(get_db),
):
    """Get daily work targets based on annual goals and YTD progress."""
    return await compute_daily_targets(db)


@router.get("/throughput/work-queue")
async def get_work_queue_endpoint(
    family_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get prioritized work queue."""
    return await get_work_queue(db, family_id=family_id)
