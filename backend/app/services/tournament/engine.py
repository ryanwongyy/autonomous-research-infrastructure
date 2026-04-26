import logging
from datetime import date, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.match import Match
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating
from app.models.rating_snapshot import RatingSnapshot
from app.models.tournament_run import TournamentRun
from app.services.llm.router import get_judge_provider
from app.services.tournament.judge import get_family_judge_prompt, judge_match, resolve_match
from app.services.tournament.matcher import PaperInfo, generate_batches
from app.services.tournament.rating_system import rating_system
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# Minimum papers required in a family to run a tournament
MIN_PAPERS_FOR_TOURNAMENT = 4


async def execute_all_family_tournaments():
    """Run tournaments for all eligible families (demand-based scheduling).

    Iterates over active families and runs a tournament for each one that
    has at least MIN_PAPERS_FOR_TOURNAMENT eligible papers.  Families with
    fewer papers are silently skipped.
    """
    async with async_session() as db:
        families = (
            (await db.execute(select(PaperFamily).where(PaperFamily.active.is_(True))))
            .scalars()
            .all()
        )

    results: list[dict] = []
    for family in families:
        paper_count = await _count_eligible_papers(family.id)
        if paper_count < MIN_PAPERS_FOR_TOURNAMENT:
            logger.info(
                f"Skipping family {family.id} ({family.short_name}): "
                f"only {paper_count} eligible papers (need {MIN_PAPERS_FOR_TOURNAMENT})"
            )
            results.append(
                {
                    "family_id": family.id,
                    "status": "skipped",
                    "reason": f"only {paper_count} papers",
                }
            )
            continue

        # Create a run record for this family
        async with async_session() as db:
            run = TournamentRun(status="running", family_id=family.id)
            db.add(run)
            await db.commit()
            await db.refresh(run)

        logger.info(
            f"Starting tournament for family {family.id} ({family.short_name}) "
            f"with {paper_count} papers — run {run.id}"
        )
        try:
            await execute_tournament_run(run.id, family_id=family.id)
            results.append(
                {
                    "family_id": family.id,
                    "run_id": run.id,
                    "status": "completed",
                }
            )
        except Exception as e:
            logger.error("Tournament for family %s failed: %s", family.id, e)
            results.append(
                {
                    "family_id": family.id,
                    "run_id": run.id,
                    "status": "failed",
                    "error": str(e),
                }
            )

    logger.info("All-family tournament sweep finished: %s", results)
    return results


async def _count_eligible_papers(family_id: str) -> int:
    """Return the number of published papers in a family."""
    async with async_session() as db:
        count = (
            await db.execute(
                select(func.count())
                .select_from(Paper)
                .where(Paper.family_id == family_id, Paper.status == "published")
            )
        ).scalar() or 0
    return count


async def execute_tournament_run(run_id: int, family_id: str | None = None):
    """Execute a full tournament run with batched matches.

    When *family_id* is provided the paper pool, ratings, and ranking are
    all scoped to that single family.  When ``None`` the legacy global
    behaviour is used (kept for backward-compatibility but discouraged).
    """
    async with async_session() as db:
        try:
            # ----- build paper pool -----
            pool_query = (
                select(Paper, Rating)
                .join(Rating, Paper.id == Rating.paper_id)
                .where(Paper.status == "published")
            )
            if family_id:
                pool_query = pool_query.where(Paper.family_id == family_id)

            results = (await db.execute(pool_query)).all()

            papers = [
                PaperInfo(
                    id=paper.id,
                    source=paper.source,
                    matches_played=rating.matches_played,
                    family_id=paper.family_id,
                )
                for paper, rating in results
            ]

            # Count by source for the run record
            benchmark_count = sum(1 for p in papers if p.source == "benchmark")
            ai_count = len(papers) - benchmark_count

            if len(papers) < 2:
                logger.warning(
                    f"Not enough papers for tournament "
                    f"(family={family_id}, pool={len(papers)}, need >= 2)"
                )
                await _update_run_status(
                    db,
                    run_id,
                    "failed",
                    0,
                    0,
                    papers_in_pool=len(papers),
                    benchmark_papers=benchmark_count,
                    ai_papers=ai_count,
                )
                return

            # ----- load family for judge prompt -----
            family_obj: PaperFamily | None = None
            if family_id:
                family_obj = (
                    await db.execute(select(PaperFamily).where(PaperFamily.id == family_id))
                ).scalar_one_or_none()

            # ----- generate batches (within-family) -----
            batches = generate_batches(
                papers,
                num_batches=settings.tournament_batches,
                matches_per_batch=settings.tournament_matches_per_batch,
                family_id=family_id,
            )

            # ----- get judge provider -----
            provider, model = await get_judge_provider()

            # ----- build family-specific judge prompt -----
            family_prompt: str | None = None
            if family_obj:
                family_prompt = get_family_judge_prompt(family_obj)

            total_matches = 0
            for batch_num, batch in enumerate(batches, 1):
                for paper_a_id, paper_b_id in batch:
                    try:
                        await _execute_single_match(
                            db,
                            run_id,
                            batch_num,
                            paper_a_id,
                            paper_b_id,
                            provider,
                            model,
                            family_id=family_id,
                            family_prompt=family_prompt,
                        )
                        total_matches += 1
                    except Exception as e:
                        logger.error("Match failed (%s vs %s): %s", paper_a_id, paper_b_id, e)

            # ----- recompute ranks WITHIN the family -----
            await _recompute_ranks(db, family_id=family_id)

            # ----- save rating snapshots -----
            await _save_snapshots(db, family_id=family_id)

            # ----- calibration score (if calibrator available) -----
            calibration_score: float | None = None
            if family_id:
                try:
                    from app.services.tournament.judge_calibrator import run_calibration_check

                    cal_report = await run_calibration_check(db, family_id, judge_model=model)
                    calibration_score = cal_report.get("discrimination_score")
                except Exception as e:
                    logger.warning("Calibration check skipped for %s: %s", family_id, e)

            # ----- update run status -----
            await _update_run_status(
                db,
                run_id,
                "completed",
                total_matches,
                len(batches),
                papers_in_pool=len(papers),
                benchmark_papers=benchmark_count,
                ai_papers=ai_count,
                judge_calibration_score=calibration_score,
            )

        except Exception as e:
            logger.error("Tournament run %d failed: %s", run_id, e)
            async with async_session() as err_db:
                await _update_run_status(err_db, run_id, "failed", 0, 0)


async def _execute_single_match(
    db: AsyncSession,
    run_id: int,
    batch_num: int,
    paper_a_id: str,
    paper_b_id: str,
    provider,
    model: str,
    family_id: str | None = None,
    family_prompt: str | None = None,
):
    """Execute a single position-swapped match."""
    # Get paper content
    paper_a = (await db.execute(select(Paper).where(Paper.id == paper_a_id))).scalar_one()
    paper_b = (await db.execute(select(Paper).where(Paper.id == paper_b_id))).scalar_one()
    rating_a = (await db.execute(select(Rating).where(Rating.paper_id == paper_a_id))).scalar_one()
    rating_b = (await db.execute(select(Rating).where(Rating.paper_id == paper_b_id))).scalar_one()

    # Use abstract as content if no PDF available
    content_a = paper_a.abstract or f"Title: {paper_a.title}"
    content_b = paper_b.abstract or f"Title: {paper_b.title}"

    # ----- detect integrity issues -----
    integrity_penalty_a = _has_integrity_issue(paper_a)
    integrity_penalty_b = _has_integrity_issue(paper_b)

    # Run position-swapped judgment (using family-specific prompt if available)
    result_a_first, result_b_first = await judge_match(
        provider=provider,
        model=model,
        paper_a_content=content_a,
        paper_b_content=content_b,
        paper_a_title=paper_a.title,
        paper_b_title=paper_b.title,
        system_prompt_override=family_prompt,
    )

    # Resolve final result
    final_result = resolve_match(result_a_first.winner, result_b_first.winner)

    # ----- apply integrity penalties -----
    # A paper with an integrity issue automatically loses unless both have issues
    if integrity_penalty_a and not integrity_penalty_b:
        final_result = "b_wins"
    elif integrity_penalty_b and not integrity_penalty_a:
        final_result = "a_wins"
    # If both have issues, keep the judge's result as-is

    # Update ratings
    update_a, update_b = rating_system.process_match(
        a_mu=rating_a.mu,
        a_sigma=rating_a.sigma,
        a_elo=rating_a.elo,
        b_mu=rating_b.mu,
        b_sigma=rating_b.sigma,
        b_elo=rating_b.elo,
        result=final_result,
    )

    # Determine winner
    winner_id = None
    if final_result == "a_wins":
        winner_id = paper_a_id
    elif final_result == "b_wins":
        winner_id = paper_b_id

    # Save match with family_id and integrity flags
    match = Match(
        tournament_run_id=run_id,
        paper_a_id=paper_a_id,
        paper_b_id=paper_b_id,
        winner_id=winner_id,
        judge_model=model,
        judge_prompt=family_prompt[:2000] if family_prompt else None,
        judgment_a_first=result_a_first.raw_response,
        judgment_b_first=result_b_first.raw_response,
        result_a_first=result_a_first.winner,
        result_b_first=result_b_first.winner,
        final_result=final_result,
        batch_number=batch_num,
        mu_change_a=update_a.mu_change,
        mu_change_b=update_b.mu_change,
        elo_change_a=update_a.elo_change,
        elo_change_b=update_b.elo_change,
        family_id=family_id,
        integrity_penalty_a=integrity_penalty_a,
        integrity_penalty_b=integrity_penalty_b,
    )
    db.add(match)

    # Update ratings
    rating_a.mu = update_a.mu
    rating_a.sigma = update_a.sigma
    rating_a.conservative_rating = update_a.conservative_rating
    rating_a.elo = update_a.elo
    rating_a.matches_played += 1
    if final_result == "a_wins":
        rating_a.wins += 1
        rating_b.losses += 1
    elif final_result == "b_wins":
        rating_a.losses += 1
        rating_b.wins += 1
    else:
        rating_a.draws += 1
        rating_b.draws += 1

    rating_b.mu = update_b.mu
    rating_b.sigma = update_b.sigma
    rating_b.conservative_rating = update_b.conservative_rating
    rating_b.elo = update_b.elo
    rating_b.matches_played += 1

    await db.commit()


def _has_integrity_issue(paper: Paper) -> bool:
    """Check whether a paper has a material provenance/replication failure.

    Inspects ``metadata_json`` for an ``integrity_flags`` key.  Any flag
    value of ``"fail"`` triggers the penalty.
    """
    meta = safe_json_loads(paper.metadata_json, {})
    flags = meta.get("integrity_flags", {})
    return any(v == "fail" for v in flags.values())


async def _recompute_ranks(db: AsyncSession, family_id: str | None = None):
    """Recompute ranks and confidence intervals within a family."""
    query = select(Rating).order_by(Rating.conservative_rating.desc())
    if family_id:
        query = query.where(Rating.family_id == family_id)

    ratings = (await db.execute(query)).scalars().all()

    for i, rating in enumerate(ratings, 1):
        rating.rank = i
        # Compute 95% confidence interval for TrueSkill rating
        rating.confidence_lower = rating.mu - 1.96 * rating.sigma
        rating.confidence_upper = rating.mu + 1.96 * rating.sigma

    await db.commit()


async def _save_snapshots(db: AsyncSession, family_id: str | None = None):
    """Save daily rating snapshots for progression charts."""
    today = date.today()

    query = select(Rating)
    if family_id:
        query = query.where(Rating.family_id == family_id)

    ratings = (await db.execute(query)).scalars().all()
    for rating in ratings:
        # Check if snapshot already exists for today
        existing = (
            await db.execute(
                select(RatingSnapshot).where(
                    RatingSnapshot.paper_id == rating.paper_id,
                    RatingSnapshot.snapshot_date == today,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.mu = rating.mu
            existing.sigma = rating.sigma
            existing.conservative_rating = rating.conservative_rating
            existing.elo = rating.elo
        else:
            snapshot = RatingSnapshot(
                paper_id=rating.paper_id,
                mu=rating.mu,
                sigma=rating.sigma,
                conservative_rating=rating.conservative_rating,
                elo=rating.elo,
                snapshot_date=today,
                family_id=family_id,
            )
            db.add(snapshot)

    await db.commit()


async def _update_run_status(
    db: AsyncSession,
    run_id: int,
    status: str,
    matches: int,
    batches: int,
    papers_in_pool: int = 0,
    benchmark_papers: int = 0,
    ai_papers: int = 0,
    judge_calibration_score: float | None = None,
):
    values = dict(
        status=status,
        completed_at=datetime.utcnow() if status != "running" else None,
        total_matches=matches,
        total_batches=batches,
        papers_in_pool=papers_in_pool,
        benchmark_papers=benchmark_papers,
        ai_papers=ai_papers,
    )
    if judge_calibration_score is not None:
        values["judge_calibration_score"] = judge_calibration_score

    await db.execute(update(TournamentRun).where(TournamentRun.id == run_id).values(**values))
    await db.commit()
