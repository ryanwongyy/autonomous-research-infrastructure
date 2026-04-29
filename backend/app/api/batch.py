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
    family_id: str | None = Field(
        default=None, description="Target family (null = auto-select)"
    )


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
            (
                await session.execute(
                    select(PaperFamily).where(PaperFamily.active.is_(True))
                )
            )
            .scalars()
            .all()
        )

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
    generated = 0  # final_status == "completed"
    killed: dict[str, int] = {}  # final_status starts with "killed_at_<stage>"
    reviewed = 0
    errors = 0  # uncaught exceptions

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

    for i, fid in enumerate(family_ids[: body.count]):
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
            final_status = report.get("final_status", "unknown")
            stage_errors = _extract_stage_errors(report)
            stage_details = _extract_stage_details(report)
            stages_completed = _extract_stages_completed(report)
            entry["generation"] = {
                "status": final_status,
                "duration_sec": report.get("total_duration_sec", 0),
                # Surface the underlying exception(s) so cron / GitHub Actions
                # logs are self-diagnosing. Without this, killed_at_* status
                # values look identical to one another in the response payload.
                #
                # Three sources, in priority order:
                #   1. The report's top-level error_message (set by the
                #      orchestrator's main except handler — covers crashes
                #      that happen OUTSIDE any stage, e.g. between stages).
                #   2. A failed stage's error string.
                #   3. None when nothing failed.
                "error_message": (
                    report.get("error_message")
                    or _primary_error_message(stage_errors, final_status)
                ),
                "error_class": report.get("error_class"),
                # Truncated traceback — enough to identify the file/line
                # without dumping kilobytes into the cron log.
                "error_traceback": _truncate_traceback(report.get("error_traceback")),
                "stage_errors": stage_errors,
                # Structured side-data from failed stages (e.g. Scout's
                # per-idea screening scores). Empty when no stage attached
                # any details beyond a simple error string.
                "stage_details": stage_details,
                # Names of stages that recorded a status — tells us how
                # far the pipeline progressed before any crash.
                "stages_completed": stages_completed,
            }
            if final_status == "completed":
                generated += 1
            elif final_status.startswith("killed_at_"):
                killed[final_status] = killed.get(final_status, 0) + 1
            # Anything else (e.g. "unknown") falls through to the success path
            # but is not counted as generated.
        except Exception as e:
            logger.error(
                "Generation failed for paper %s: %s", paper_id, e, exc_info=True
            )
            entry["generation"] = {
                "status": "error",
                "error_message": str(e),
                "error_class": type(e).__name__,
            }
            errors += 1
            results.append(entry)
            continue

        # --- Review (only if generation truly completed) ---
        if entry["generation"]["status"] == "completed":
            try:
                async with async_session() as session:
                    review_report = await run_review_pipeline(session, paper_id)
                entry["review"] = {
                    "decision": review_report.get("decision", "unknown"),
                }
                reviewed += 1
            except Exception as e:
                logger.warning("Review failed for paper %s: %s", paper_id, e)
                entry["review"] = {
                    "status": "error",
                    "error_message": str(e),
                    "error_class": type(e).__name__,
                }

        results.append(entry)

    # Build summary that distinguishes generated / killed / errors so a cron
    # showing "0 generated" is unmistakable, no matter how the failures were
    # shaped.
    summary_parts = [f"Generated {generated}", f"reviewed {reviewed}"]
    if killed:
        for stage, n in sorted(killed.items()):
            summary_parts.append(f"{stage} {n}")
    if errors:
        summary_parts.append(f"errors {errors}")
    summary = ", ".join(summary_parts)

    return BatchResult(
        action="generate",
        results=results,
        summary=summary,
    )


def _extract_stage_errors(report: dict[str, Any]) -> dict[str, str]:
    """Pull per-stage error strings out of a pipeline report.

    The orchestrator's ``_run_stage`` records ``{"status": "failed",
    "error": str(e)}`` for any stage that raised. Surface those exception
    texts in the batch response so the operator can see WHICH stage failed
    and WHY without owning the backend's runtime logs.
    """
    out: dict[str, str] = {}
    for stage_name, stage_report in (report.get("stages") or {}).items():
        if not isinstance(stage_report, dict):
            continue
        if stage_report.get("status") == "failed":
            err = (
                stage_report.get("error")
                or stage_report.get("reason")
                or "(no error message)"
            )
            out[stage_name] = str(err)
    return out


# Stage-report keys that aren't useful in the API response — they're
# infrastructure / timing fields, not diagnostic content.
_STAGE_INFRA_KEYS = frozenset(
    {"status", "stage_name", "duration_sec", "error", "reason"}
)


def _extract_stage_details(report: dict[str, Any]) -> dict[str, Any]:
    """Pull structured side-data from each FAILED stage's report.

    Stages that fail in interesting ways attach extra fields to their
    return dict beyond ``status`` / ``error``. Scout, for example, returns
    ``screenings`` — a list of per-idea screening scores — when no idea
    cleared the threshold. Surfacing those lets the operator see WHY each
    candidate idea was rejected (composite < 4? novelty < 4? data < 4?)
    without needing Render runtime logs.

    The infra-only keys (status, stage_name, duration_sec, error, reason)
    are filtered out — they're already in ``stage_errors`` or the entry's
    top-level ``status`` / ``duration_sec`` fields.
    """
    out: dict[str, Any] = {}
    for stage_name, stage_report in (report.get("stages") or {}).items():
        if not isinstance(stage_report, dict):
            continue
        if stage_report.get("status") != "failed":
            continue
        details = {k: v for k, v in stage_report.items() if k not in _STAGE_INFRA_KEYS}
        if details:
            out[stage_name] = details
    return out


def _primary_error_message(
    stage_errors: dict[str, str], final_status: str
) -> str | None:
    """Pick the most relevant single error string for the response.

    For ``killed_at_<stage>`` final statuses, prefer that stage's error.
    Otherwise return the first failed stage's error, or None.
    """
    if not stage_errors:
        return None
    if final_status.startswith("killed_at_"):
        stage_name = final_status[len("killed_at_") :]
        if stage_name in stage_errors:
            return stage_errors[stage_name]
    return next(iter(stage_errors.values()))


def _extract_stages_completed(report: dict[str, Any]) -> list[str]:
    """List the names of every stage that recorded a status in the report.

    Useful when the orchestrator's main except handler fires (e.g.
    ``await None`` crash between stages). The presence of e.g.
    ``["scout", "designer", "data_steward", "analyst"]`` tells us the
    crash happened AFTER analyst completed but before drafter recorded
    any status.
    """
    stages = report.get("stages") or {}
    return list(stages.keys()) if isinstance(stages, dict) else []


def _truncate_traceback(tb: str | None, limit: int = 4000) -> str | None:
    """Trim a traceback so the response payload stays small.

    Keeps the head (where the crash usually points) and the tail
    (where the most-recently-called frame appears in Python format).
    """
    if not tb:
        return None
    if len(tb) <= limit:
        return tb
    head = tb[: limit // 2]
    tail = tb[-limit // 2 :]
    return f"{head}\n... [truncated] ...\n{tail}"


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
            (
                await session.execute(
                    select(Paper.id).where(
                        Paper.review_status == "awaiting",
                        Paper.funnel_stage.in_(["candidate", "reviewing", "benchmark"]),
                        Paper.status != "killed",
                    )
                )
            )
            .scalars()
            .all()
        )

    for paper_id in pending:
        try:
            async with async_session() as session:
                report = await run_review_pipeline(session, paper_id)
            results.append(
                {
                    "paper_id": paper_id,
                    "decision": report.get("decision", "unknown"),
                }
            )
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
            (
                await session.execute(
                    select(Paper.id).where(
                        Paper.release_status == "internal",
                        Paper.review_status == "peer_reviewed",
                        Paper.status != "killed",
                    )
                )
            )
            .scalars()
            .all()
        )

    promoted = 0
    blocked = 0

    for paper_id in eligible:
        async with async_session() as session:
            check = await check_transition_preconditions(session, paper_id, "candidate")

            if check["can_transition"]:
                await transition_release_status(
                    session, paper_id, "candidate", approved_by="batch_auto_promote"
                )
                await session.commit()
                results.append({"paper_id": paper_id, "promoted": True})
                promoted += 1
            else:
                results.append(
                    {
                        "paper_id": paper_id,
                        "promoted": False,
                        "blockers": check["blockers"],
                    }
                )
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
        existing = (await session.execute(select(PaperFamily.id))).scalars().all()
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
