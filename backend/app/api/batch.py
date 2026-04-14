"""Batch orchestration endpoints for autonomous pipeline operation.

Called by GitHub Actions cron to drive the full generate -> review -> tournament -> promote loop.
All endpoints are synchronous (not BackgroundTask) so the caller can wait for results
and keep the Render process alive for the duration.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.database import async_session
from app.models.paper import Paper
from app.models.paper_family import PaperFamily

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    count: int = Field(default=2, ge=1, le=10, description="Papers to generate per run")
    family_id: str | None = Field(default=None, description="Target family (null = auto-select)")


class BatchResult(BaseModel):
    action: str
    results: list[dict[str, Any]]
    summary: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _pick_underserved_families(count: int) -> list[str]:
    """Return family IDs with the fewest papers, up to *count*."""
    async with async_session() as session:
        families = (
            await session.execute(
                select(PaperFamily).where(PaperFamily.active.is_(True))
            )
        ).scalars().all()

        if not families:
            return []

        counts: list[tuple[str, int]] = []
        for fam in families:
            paper_count = (
                await session.execute(
                    select(func.count())
                    .select_from(Paper)
                    .where(Paper.family_id == fam.id)
                )
            ).scalar() or 0
            counts.append((fam.id, paper_count))

        # Sort by paper count ascending (underserved first), pick up to *count*
        counts.sort(key=lambda x: x[1])
        return [fid for fid, _ in counts[:count]]


# ---------------------------------------------------------------------------
# POST /batch/generate
# ---------------------------------------------------------------------------

@router.post("/batch/generate", response_model=BatchResult)
async def batch_generate(body: GenerateRequest, request: Request):
    """Generate papers and auto-trigger review for each.

    Runs sequentially to respect LLM rate limits and memory constraints.
    """
    from app.services.paper_generation.orchestrator import run_full_pipeline
    from app.services.review_pipeline.orchestrator import run_review_pipeline

    results: list[dict[str, Any]] = []
    generated = 0
    reviewed = 0
    errors = 0

    # Decide which families to target
    if body.family_id:
        family_ids = [body.family_id] * body.count
    else:
        family_ids = await _pick_underserved_families(body.count)
        if not family_ids:
            return BatchResult(
                action="generate",
                results=[],
                summary="No active families found. Create families first.",
            )
        # Cycle through families if count > len(family_ids)
        while len(family_ids) < body.count:
            family_ids.append(family_ids[len(family_ids) % len(family_ids)])

    for i, fid in enumerate(family_ids[:body.count]):
        paper_id = f"apep_{uuid.uuid4().hex[:8]}"
        entry: dict[str, Any] = {"paper_id": paper_id, "family_id": fid, "index": i}

        # --- Generation ---
        try:
            async with async_session() as session:
                report = await run_full_pipeline(
                    session=session,
                    family_id=fid,
                    paper_id=paper_id,
                )
            entry["generation"] = {
                "status": report.get("final_status", "unknown"),
                "duration_sec": report.get("total_duration_sec", 0),
            }
            generated += 1
        except Exception as e:
            logger.error("Generation failed for paper %s: %s", paper_id, e, exc_info=True)
            entry["generation"] = {"status": f"error: {e}"}
            errors += 1
            results.append(entry)
            continue

        # --- Review (only if generation succeeded) ---
        if report.get("final_status", "").startswith("completed"):
            try:
                async with async_session() as session:
                    review_report = await run_review_pipeline(session, paper_id)
                entry["review"] = {
                    "decision": review_report.get("decision", "unknown"),
                }
                reviewed += 1
            except Exception as e:
                logger.warning("Review failed for paper %s: %s", paper_id, e)
                entry["review"] = {"status": f"error: {e}"}

        results.append(entry)

    return BatchResult(
        action="generate",
        results=results,
        summary=f"Generated {generated}, reviewed {reviewed}, errors {errors}",
    )


# ---------------------------------------------------------------------------
# POST /batch/review-pending
# ---------------------------------------------------------------------------

@router.post("/batch/review-pending", response_model=BatchResult)
async def batch_review_pending(request: Request):
    """Find papers awaiting review and run the review pipeline on each."""
    from app.services.review_pipeline.orchestrator import run_review_pipeline

    results: list[dict[str, Any]] = []

    async with async_session() as session:
        pending = (
            await session.execute(
                select(Paper.id).where(
                    Paper.review_status == "awaiting",
                    Paper.funnel_stage.in_(["candidate", "reviewing", "benchmark"]),
                    Paper.status != "killed",
                )
            )
        ).scalars().all()

    for paper_id in pending:
        try:
            async with async_session() as session:
                report = await run_review_pipeline(session, paper_id)
            results.append({
                "paper_id": paper_id,
                "decision": report.get("decision", "unknown"),
            })
        except Exception as e:
            logger.warning("Review failed for %s: %s", paper_id, e)
            results.append({"paper_id": paper_id, "error": str(e)})

    return BatchResult(
        action="review-pending",
        results=results,
        summary=f"Reviewed {len(results)} pending papers",
    )


# ---------------------------------------------------------------------------
# POST /batch/tournament
# ---------------------------------------------------------------------------

@router.post("/batch/tournament", response_model=BatchResult)
async def batch_tournament(request: Request):
    """Run tournaments for all eligible families."""
    from app.services.tournament.engine import execute_all_family_tournaments

    try:
        family_results = await execute_all_family_tournaments()
        completed = sum(1 for r in family_results if r.get("status") == "completed")
        skipped = sum(1 for r in family_results if r.get("status") == "skipped")
        failed = sum(1 for r in family_results if r.get("status") == "failed")

        return BatchResult(
            action="tournament",
            results=family_results,
            summary=f"Tournaments: {completed} completed, {skipped} skipped, {failed} failed",
        )
    except Exception as e:
        logger.error("Tournament batch failed: %s", e, exc_info=True)
        return BatchResult(
            action="tournament",
            results=[{"error": str(e)}],
            summary=f"Tournament batch error: {e}",
        )


# ---------------------------------------------------------------------------
# POST /batch/promote
# ---------------------------------------------------------------------------

@router.post("/batch/promote", response_model=BatchResult)
async def batch_promote(request: Request):
    """Auto-promote papers from internal -> candidate where preconditions are met."""
    from app.services.release.release_manager import (
        check_transition_preconditions,
        transition_release_status,
    )

    results: list[dict[str, Any]] = []

    async with async_session() as session:
        # Papers that are reviewed and still internal
        eligible = (
            await session.execute(
                select(Paper.id).where(
                    Paper.release_status == "internal",
                    Paper.review_status == "peer_reviewed",
                    Paper.status != "killed",
                )
            )
        ).scalars().all()

    promoted = 0
    blocked = 0

    for paper_id in eligible:
        async with async_session() as session:
            check = await check_transition_preconditions(session, paper_id, "candidate")

            if check["can_transition"]:
                result = await transition_release_status(
                    session, paper_id, "candidate", approved_by="batch_auto_promote"
                )
                await session.commit()
                results.append({"paper_id": paper_id, "promoted": True})
                promoted += 1
            else:
                results.append({
                    "paper_id": paper_id,
                    "promoted": False,
                    "blockers": check["blockers"],
                })
                blocked += 1

    return BatchResult(
        action="promote",
        results=results,
        summary=f"Promoted {promoted}, blocked {blocked} (of {len(eligible)} eligible)",
    )


# ---------------------------------------------------------------------------
# POST /batch/seed-families
# ---------------------------------------------------------------------------

@router.post("/batch/seed-families", response_model=BatchResult)
async def batch_seed_families(request: Request):
    """Seed the 11 paper families if not already present."""
    from seeds.families import FAMILIES

    results: list[dict[str, Any]] = []

    async with async_session() as session:
        existing = (
            await session.execute(select(PaperFamily.id))
        ).scalars().all()
        existing_ids = set(existing)

        inserted = 0
        for fam in FAMILIES:
            if fam["id"] in existing_ids:
                results.append({"family_id": fam["id"], "status": "already_exists"})
                continue

            family = PaperFamily(**fam)
            session.add(family)
            results.append({"family_id": fam["id"], "status": "created"})
            inserted += 1

        await session.commit()

    return BatchResult(
        action="seed-families",
        results=results,
        summary=f"Seeded {inserted} families ({len(existing_ids)} already existed)",
    )
