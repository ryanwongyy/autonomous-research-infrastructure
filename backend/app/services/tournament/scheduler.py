import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from app.config import settings
from app.database import async_session
from app.models.paper import Paper
from app.models.paper_family import PaperFamily

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# Minimum papers a family needs before we run a tournament for it
MIN_PAPERS_FOR_TOURNAMENT = 4


async def _get_eligible_families() -> list[dict]:
    """Return active families that have enough published papers for a tournament.

    Each entry is ``{"family_id": str, "short_name": str, "paper_count": int}``.
    """
    async with async_session() as db:
        families = (
            (await db.execute(select(PaperFamily).where(PaperFamily.active.is_(True))))
            .scalars()
            .all()
        )

        eligible: list[dict] = []
        for fam in families:
            count = (
                await db.execute(
                    select(func.count())
                    .select_from(Paper)
                    .where(
                        Paper.family_id == fam.id,
                        Paper.status == "published",
                    )
                )
            ).scalar() or 0

            if count >= MIN_PAPERS_FOR_TOURNAMENT:
                eligible.append(
                    {
                        "family_id": fam.id,
                        "short_name": fam.short_name,
                        "paper_count": count,
                    }
                )

    return eligible


async def scheduled_tournament_run():
    """Triggered daily to run demand-based family tournaments.

    Instead of a single global tournament, this checks each active family
    for paper count and runs a tournament for each eligible family in
    sequence.
    """
    from app.services.tournament.engine import execute_all_family_tournaments

    eligible = await _get_eligible_families()
    logger.info(
        f"Scheduled sweep: {len(eligible)} eligible families: {[e['family_id'] for e in eligible]}"
    )

    if not eligible:
        logger.info("No families eligible for tournament — skipping")
        return

    results = await execute_all_family_tournaments()
    completed = sum(1 for r in results if r.get("status") == "completed")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    failed = sum(1 for r in results if r.get("status") == "failed")

    logger.info(
        f"Scheduled sweep finished: {completed} completed, {skipped} skipped, {failed} failed"
    )


def setup_scheduler():
    """Configure the daily tournament scheduler."""
    scheduler.add_job(
        scheduled_tournament_run,
        "cron",
        hour=settings.tournament_schedule_hour,
        minute=settings.tournament_schedule_minute,
        id="daily_family_tournament",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"Tournament scheduler started: daily at "
        f"{settings.tournament_schedule_hour:02d}:"
        f"{settings.tournament_schedule_minute:02d} UTC "
        f"(family-local mode)"
    )


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
