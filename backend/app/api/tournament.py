import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.match import Match
from app.models.tournament_run import TournamentRun
from app.models.paper_family import PaperFamily
from app.schemas.match import MatchResponse
from app.services.tournament.engine import execute_all_family_tournaments, execute_tournament_run

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/tournament/run")
@limiter.limit("5/hour")
async def trigger_tournament_run(
    request: Request,
    background_tasks: BackgroundTasks,
    family_id: str = Query(
        ...,
        description=(
            'Family ID to run the tournament for, or "all" to run for all eligible families.'
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a tournament run for a specific family or all eligible families.

    ``family_id`` is required.  Pass ``"all"`` to run the demand-based sweep
    across every active family.
    """
    if family_id == "all":
        # Run for all eligible families
        background_tasks.add_task(execute_all_family_tournaments)
        return {"status": "started", "family_id": "all", "message": "Running for all eligible families"}

    # Validate that the family exists
    family = (
        await db.execute(
            select(PaperFamily).where(PaperFamily.id == family_id)
        )
    ).scalar_one_or_none()

    if not family:
        raise HTTPException(status_code=404, detail=f"Family '{family_id}' not found")

    # Atomic check-then-create inside a savepoint to prevent race conditions
    try:
        async with db.begin_nested():
            running = (
                await db.execute(
                    select(TournamentRun).where(
                        TournamentRun.status == "running",
                        TournamentRun.family_id == family_id,
                    )
                )
            ).scalar_one_or_none()

            if running:
                raise HTTPException(
                    status_code=409,
                    detail=f"A tournament run is already in progress for family '{family_id}'",
                )

            run = TournamentRun(status="running", family_id=family_id)
            db.add(run)
        await db.commit()
        await db.refresh(run)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to create tournament run")
        raise HTTPException(status_code=500, detail="Failed to create tournament run")

    background_tasks.add_task(execute_tournament_run, run.id, family_id)

    return {
        "run_id": run.id,
        "family_id": family_id,
        "family_name": family.short_name,
        "status": "started",
    }


@router.get("/tournament/runs")
async def list_tournament_runs(
    family_id: str | None = Query(None, description="Filter by family ID"),
    db: AsyncSession = Depends(get_db),
):
    """List recent tournament runs, optionally filtered by family."""
    query = select(TournamentRun).order_by(TournamentRun.started_at.desc()).limit(50)

    if family_id:
        query = query.where(TournamentRun.family_id == family_id)

    results = (await db.execute(query)).scalars().all()

    return [
        {
            "id": r.id,
            "family_id": r.family_id,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "total_matches": r.total_matches,
            "total_batches": r.total_batches,
            "papers_in_pool": r.papers_in_pool,
            "benchmark_papers": r.benchmark_papers,
            "ai_papers": r.ai_papers,
            "judge_calibration_score": r.judge_calibration_score,
            "status": r.status,
        }
        for r in results
    ]


@router.get("/tournament/runs/{run_id}")
async def get_tournament_run(run_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed info for a single tournament run, including matches and family info."""
    run = (
        await db.execute(select(TournamentRun).where(TournamentRun.id == run_id))
    ).scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Tournament run not found")

    matches = (
        await db.execute(
            select(Match)
            .where(Match.tournament_run_id == run_id)
            .order_by(Match.batch_number, Match.id)
            .limit(1000)
        )
    ).scalars().all()

    # Load family info if present
    family_info = None
    if run.family_id:
        family = (
            await db.execute(
                select(PaperFamily).where(PaperFamily.id == run.family_id)
            )
        ).scalar_one_or_none()
        if family:
            family_info = {
                "id": family.id,
                "name": family.name,
                "short_name": family.short_name,
                "lock_protocol_type": family.lock_protocol_type,
            }

    return {
        "id": run.id,
        "family_id": run.family_id,
        "family": family_info,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "total_matches": run.total_matches,
        "total_batches": run.total_batches,
        "papers_in_pool": run.papers_in_pool,
        "benchmark_papers": run.benchmark_papers,
        "ai_papers": run.ai_papers,
        "judge_calibration_score": run.judge_calibration_score,
        "status": run.status,
        "matches": [MatchResponse.model_validate(m) for m in matches],
    }
