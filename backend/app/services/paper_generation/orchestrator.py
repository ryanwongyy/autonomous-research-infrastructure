"""Main orchestrator: sequences bounded roles with boundary enforcement.

Pipeline:
1. Scout     -> generates and screens ideas
2. Designer  -> creates research design, locks it
3. Data Steward -> builds source manifest, fetches data
4. Analyst   -> generates and runs analysis code
5. Drafter   -> composes manuscript with evidence constraints
5.5 Collegial Review -> constructive multi-turn dialogue with colleagues
6. Verifier  -> cross-checks claims (read-only)
7. Packager  -> assembles immutable package

Hard lock enforcement: any boundary violation raises PipelineViolationError.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
import uuid
from typing import Any

import yaml
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating
from app.models.source_card import SourceCard
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider
from app.services.paper_generation.boundary_enforcer import (
    PipelineViolationError,
    verify_lock_integrity,
)
from app.services.paper_generation.roles.scout import generate_ideas, screen_idea
from app.services.paper_generation.roles.designer import (
    create_research_design,
    lock_design,
)
from app.services.paper_generation.roles.data_steward import (
    build_source_manifest,
    fetch_and_snapshot,
)
from app.services.paper_generation.roles.analyst import (
    generate_analysis_code,
    execute_analysis,
)
from app.services.paper_generation.roles.drafter import compose_manuscript
from app.services.paper_generation.roles.verifier import verify_manuscript
from app.services.paper_generation.roles.packager import build_package

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


async def run_full_pipeline(
    session: AsyncSession | None = None,
    family_id: str = "F1",
    paper_id: str | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Run the complete paper generation pipeline.

    Each stage runs in its OWN AsyncSession (= its own DB connection
    from the pool). This avoids holding a single connection across
    10+ minutes of LLM work — Postgres / network providers tend to
    drop long-idle connections, and a stale connection makes even
    ``commit()`` and ``rollback()`` raise InterfaceError (production
    run #25133985204 hit this exact symptom).

    The ``session`` parameter is kept for backward compatibility with
    callers that pass one in (and tests that monkeypatch this function
    on the kwarg shape) but is **ignored** — every stage opens a fresh
    session via ``async_session()``. State propagates across stages
    via the database (each stage commits its writes, the next stage
    queries fresh).

    Returns pipeline report with timing, status per stage, and final paper_id.
    """
    del session  # explicitly ignored; see docstring

    pipeline_start = time.monotonic()

    # Resolve provider once for all roles
    if provider is None:
        provider, model = await get_generation_provider()

    # Generate paper ID if not provided
    if not paper_id:
        paper_id = f"apep_{uuid.uuid4().hex[:8]}"

    report: dict[str, Any] = {
        "paper_id": paper_id,
        "family_id": family_id,
        "stages": {},
        "final_status": "unknown",
        "total_duration_sec": 0.0,
    }

    try:
        # ---------------------------------------------------------------
        # 0. Create Paper record
        # ---------------------------------------------------------------
        async with async_session() as s:
            await _ensure_paper(s, paper_id, family_id)
            await s.commit()

        # ---------------------------------------------------------------
        # 1. SCOUT: generate and screen ideas
        # ---------------------------------------------------------------
        stage_report = await _run_stage_with_session(
            "scout",
            _stage_scout,
            paper_id,
            family_id=family_id,
            provider=provider,
        )
        report["stages"]["scout"] = stage_report
        if stage_report["status"] == "failed":
            report["final_status"] = "killed_at_scout"
            return _finalise_report(report, pipeline_start)

        idea_card = stage_report.get("idea_card", {})

        # ---------------------------------------------------------------
        # 2. DESIGNER: create research design and lock it
        # ---------------------------------------------------------------
        stage_report = await _run_stage_with_session(
            "designer",
            _stage_designer,
            paper_id,
            idea_card=idea_card,
            provider=provider,
        )
        report["stages"]["designer"] = stage_report
        if stage_report["status"] == "failed":
            report["final_status"] = "killed_at_designer"
            return _finalise_report(report, pipeline_start)

        # ---------------------------------------------------------------
        # 3. DATA STEWARD: build source manifest and fetch data
        # ---------------------------------------------------------------
        stage_report = await _run_stage_with_session(
            "data_steward",
            _stage_data_steward,
            paper_id,
            provider=provider,
        )
        report["stages"]["data_steward"] = stage_report
        if stage_report["status"] == "failed":
            report["final_status"] = "killed_at_data_steward"
            return _finalise_report(report, pipeline_start)

        source_manifest = stage_report.get("source_manifest", {})

        # ---------------------------------------------------------------
        # 4. ANALYST: generate and run analysis code
        # ---------------------------------------------------------------
        stage_report = await _run_stage_with_session(
            "analyst",
            _stage_analyst,
            paper_id,
            provider=provider,
        )
        report["stages"]["analyst"] = stage_report
        if stage_report["status"] == "failed":
            report["final_status"] = "killed_at_analyst"
            return _finalise_report(report, pipeline_start)

        code_content = stage_report.get("code_content", "")
        result_manifest = stage_report.get("result_manifest", {})

        # ---------------------------------------------------------------
        # 5. DRAFTER: compose manuscript
        # ---------------------------------------------------------------
        stage_report = await _run_stage_with_session(
            "drafter",
            _stage_drafter,
            paper_id,
            result_manifest=result_manifest,
            source_manifest=source_manifest,
            provider=provider,
        )
        report["stages"]["drafter"] = stage_report
        if stage_report["status"] == "failed":
            report["final_status"] = "killed_at_drafter"
            return _finalise_report(report, pipeline_start)

        manuscript_latex = stage_report.get("manuscript_latex", "")

        # ---------------------------------------------------------------
        # 5.5. COLLEGIAL REVIEW: constructive multi-turn feedback
        # ---------------------------------------------------------------
        stage_report = await _run_stage_with_session(
            "collegial_review",
            _stage_collegial_review,
            paper_id,
            manuscript_latex=manuscript_latex,
            provider=provider,
        )
        report["stages"]["collegial_review"] = stage_report
        # Collegial review cannot kill a paper — it only strengthens it
        # Use the revised manuscript if available
        if stage_report.get("revised_manuscript"):
            manuscript_latex = stage_report["revised_manuscript"]

        # ---------------------------------------------------------------
        # 6. VERIFIER: cross-check claims
        # ---------------------------------------------------------------
        stage_report = await _run_stage_with_session(
            "verifier",
            _stage_verifier,
            paper_id,
            result_manifest=result_manifest,
            provider=provider,
        )
        report["stages"]["verifier"] = stage_report

        verification_report = stage_report.get("verification", {})
        recommendation = verification_report.get("summary", {}).get(
            "recommendation", "revise"
        )

        # If verifier recommends rejection, kill the paper
        if recommendation == "reject":
            async with async_session() as s:
                paper = await _reload_paper(s, paper_id)
                paper.funnel_stage = "killed"
                paper.kill_reason = "Verifier recommended rejection"
                s.add(paper)
                await s.commit()
            report["final_status"] = "rejected_by_verifier"
            return _finalise_report(report, pipeline_start)

        # ---------------------------------------------------------------
        # 7. PACKAGER: assemble final package
        # ---------------------------------------------------------------
        stage_report = await _run_stage_with_session(
            "packager",
            _stage_packager,
            paper_id,
            manuscript_latex=manuscript_latex,
            code_content=code_content,
            result_manifest=result_manifest,
            source_manifest=source_manifest,
            verification_report=verification_report,
        )
        report["stages"]["packager"] = stage_report

        # ---------------------------------------------------------------
        # Pipeline complete
        # ---------------------------------------------------------------
        async with async_session() as s:
            paper = await _reload_paper(s, paper_id)
            report["final_status"] = f"completed (funnel_stage={paper.funnel_stage})"
        logger.info("Pipeline completed for paper %s", paper_id)

    except PipelineViolationError as e:
        report["final_status"] = f"boundary_violation: {e}"
        report["error_message"] = str(e)
        report["error_class"] = type(e).__name__
        report["error_traceback"] = traceback.format_exc()
        logger.error("Pipeline boundary violation for paper %s: %s", paper_id, e)
    except Exception as e:
        report["final_status"] = f"error: {e}"
        # Capture diagnostics so the cron / GitHub Actions log shows
        # exactly which line raised, without needing Render runtime logs.
        report["error_message"] = str(e)
        report["error_class"] = type(e).__name__
        report["error_traceback"] = traceback.format_exc()
        logger.error("Pipeline failed for paper %s: %s", paper_id, e, exc_info=True)
        await _set_error(paper_id, str(e))

    return _finalise_report(report, pipeline_start)


async def _run_stage_with_session(
    stage_name: str,
    stage_fn,
    paper_id: str,
    **stage_kwargs,
) -> dict[str, Any]:
    """Open a fresh DB session, reload the paper, run the stage, commit.

    Each call gets a fresh connection from the pool — pool_pre_ping
    ensures the connection is alive before use, so a connection that
    was dropped during the previous stage's LLM call gets replaced
    cleanly here rather than blowing up on the next ``commit()``.
    """
    async with async_session() as s:
        paper = await _reload_paper(s, paper_id)
        result = await _run_stage(stage_name, stage_fn, s, paper, **stage_kwargs)
        # Commit even on stage failure so partial progress (paper
        # record updates, kill_reason, etc.) persists. Each stage's
        # exception handling is inside _run_stage; nothing here raises.
        try:
            await s.commit()
        except Exception:
            await s.rollback()
            raise
    return result


# ---------------------------------------------------------------------------
# Legacy entry point (backward-compatible)
# ---------------------------------------------------------------------------


async def run_paper_generation(domain_config_id: str, paper_id: str | None = None):
    """Legacy entry point for paper generation.

    Wraps run_full_pipeline for backward compatibility with existing callers.
    Uses the default domain config mapping to resolve a family_id.
    """
    if not paper_id:
        paper_id = f"apep_{uuid.uuid4().hex[:8]}"

    # Map domain_config_id to a family_id (best-effort)
    async with async_session() as session:
        family_id = await _resolve_family_id(session, domain_config_id)
        result = await run_full_pipeline(
            session=session,
            family_id=family_id,
            paper_id=paper_id,
        )

    # Trigger review pipeline if completed
    if result.get("final_status", "").startswith("completed"):
        try:
            from app.services.review_pipeline.orchestrator import run_review_pipeline

            await run_review_pipeline(paper_id)
        except ImportError:
            logger.info("Review pipeline not available")
        except Exception as e:
            logger.warning("Review pipeline failed: %s", e)

    return result


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------


async def _stage_scout(
    session: AsyncSession,
    paper: Paper,
    *,
    family_id: str,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Scout stage: generate ideas and pick the best one."""
    ideas = await generate_ideas(
        session=session,
        family_id=family_id,
        count=5,
        provider=provider,
    )

    if not ideas:
        return {"status": "failed", "reason": "No ideas generated"}

    # Screen each idea and pick the best passing one
    best_idea = None
    best_score = -1.0
    screening_results: list[dict] = []

    for idea in ideas:
        screening = await screen_idea(
            session=session,
            idea_card=idea,
            provider=provider,
        )
        # Compact per-dimension score map: {dim: int} for the surfaced
        # screening result. Keeps payload small but tells the operator
        # exactly which dimension was the floor on each rejected idea.
        # Run #25110421840 surfaced only `composite` here, leaving us
        # unable to tell whether novelty or data_adequacy was failing.
        scores = screening.get("scores", {}) or {}
        per_dim: dict[str, int] = {}
        for dim_name, dim_data in scores.items():
            if isinstance(dim_data, dict):
                val = dim_data.get("score")
                if isinstance(val, int):
                    per_dim[dim_name] = val
        screening_results.append(
            {
                "question": idea.get("research_question", "")[:80],
                "composite": screening.get("weighted_composite", 0),
                "scores": per_dim,
                "passed": screening.get("pass", False),
            }
        )

        if screening.get("pass", False):
            score = screening.get("weighted_composite", 0)
            if score > best_score:
                best_score = score
                best_idea = idea

    if best_idea is None:
        return {
            "status": "failed",
            "reason": "No ideas passed screening",
            "screenings": screening_results,
        }

    # Store the winning idea on the paper
    idea_yaml = yaml.dump(best_idea, default_flow_style=False, sort_keys=False)
    paper.idea_card_yaml = idea_yaml
    paper.funnel_stage = "screened"
    paper.novelty_score = best_score
    session.add(paper)
    await session.flush()

    return {
        "status": "completed",
        "idea_card": best_idea,
        "screening_score": best_score,
        "ideas_generated": len(ideas),
        "ideas_passed": sum(1 for s in screening_results if s["passed"]),
        "screenings": screening_results,
    }


async def _stage_designer(
    session: AsyncSession,
    paper: Paper,
    *,
    idea_card: dict,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Designer stage: create and lock research design."""
    design_result = await create_research_design(
        session=session,
        paper_id=paper.id,
        idea_card=idea_card,
        provider=provider,
    )

    design_yaml = design_result.get("design_yaml", "")
    narrative_memo = design_result.get("narrative_memo", "")

    if not design_yaml:
        return {"status": "failed", "reason": "Empty design YAML"}

    lock_artifact = await lock_design(
        session=session,
        paper_id=paper.id,
        design_yaml=design_yaml,
        narrative_memo=narrative_memo,
        locked_by="pipeline_auto",
    )

    return {
        "status": "completed",
        "lock_version": lock_artifact.version,
        "lock_hash": lock_artifact.lock_hash[:16],
        "protocol_type": design_result.get("protocol_type", ""),
    }


async def _stage_data_steward(
    session: AsyncSession,
    paper: Paper,
    *,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Data Steward stage: build manifest and fetch data.

    The LLM building the manifest sometimes hallucinates source IDs that
    aren't in the source-card registry (e.g. ``UNREGISTERED::fpds_ng_bulk``,
    ``NONE_REGISTERED``). Without filtering, every fetch raises
    "Source card not found" and the stage returns ``failed``.

    This implementation:
      1. Loads the registered source-card IDs once.
      2. Filters the manifest's sources to only those that exist.
      3. Falls back to a small default whitelist (federal_register +
         regulations_gov) if zero valid IDs remain — these are
         broad-purpose AI-governance-relevant sources that always work.
      4. Surfaces ``reason`` on failed returns so diagnostics aren't
         the literal string "(no error message)".
    """
    source_manifest = await build_source_manifest(
        session=session,
        paper_id=paper.id,
        provider=provider,
    )

    # Load registered source-card IDs so we can drop hallucinated ones
    registered_result = await session.execute(
        select(SourceCard.id).where(SourceCard.active.is_(True))
    )
    registered_ids = {row[0] for row in registered_result.all()}

    raw_sources = source_manifest.get("sources", []) or []
    valid_sources: list[dict[str, Any]] = []
    dropped_ids: list[str] = []
    for src in raw_sources:
        sc_id = (src or {}).get("source_card_id", "")
        if sc_id in registered_ids:
            valid_sources.append(src)
        else:
            dropped_ids.append(sc_id)

    if dropped_ids:
        logger.warning(
            "Data Steward dropped %d unregistered source IDs from manifest "
            "(LLM hallucinations): %s",
            len(dropped_ids),
            dropped_ids[:5],
        )

    # Fallback: if the LLM picked zero valid IDs, use broad-purpose defaults
    # so the pipeline can still produce real data rather than dying here.
    if not valid_sources:
        fallback_ids = [
            sid
            for sid in ("federal_register", "regulations_gov")
            if sid in registered_ids
        ]
        if fallback_ids:
            logger.warning(
                "Data Steward got zero valid sources from LLM; falling back to %s",
                fallback_ids,
            )
            valid_sources = [
                {"source_card_id": sid, "fetch_params": {}} for sid in fallback_ids
            ]

    snapshots_created = 0
    fetch_errors: list[str] = []

    for source_entry in valid_sources:
        source_id = source_entry.get("source_card_id", "")
        fetch_params = source_entry.get("fetch_params")

        try:
            await fetch_and_snapshot(
                session=session,
                paper_id=paper.id,
                source_id=source_id,
                fetch_params=fetch_params,
            )
            snapshots_created += 1
        except Exception as e:
            logger.warning("Failed to snapshot source '%s': %s", source_id, e)
            fetch_errors.append(f"{source_id}: {e}")

    if snapshots_created > 0:
        return {
            "status": "completed",
            "source_manifest": source_manifest,
            "snapshots_created": snapshots_created,
            "fetch_errors": fetch_errors,
            "dropped_source_ids": dropped_ids,
        }

    # Build a useful reason string so error_message isn't "(no error message)"
    if fetch_errors:
        reason = f"All {len(fetch_errors)} source fetches failed: " + "; ".join(
            fetch_errors[:3]
        )
    elif dropped_ids:
        reason = (
            f"LLM picked {len(dropped_ids)} unregistered source IDs and the "
            f"fallback whitelist was empty. Dropped: {dropped_ids[:5]}"
        )
    else:
        reason = "Manifest contained zero sources and no fallback was configured"

    return {
        "status": "failed",
        "reason": reason,
        "source_manifest": source_manifest,
        "snapshots_created": 0,
        "fetch_errors": fetch_errors,
        "dropped_source_ids": dropped_ids,
    }


async def _stage_analyst(
    session: AsyncSession,
    paper: Paper,
    *,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Analyst stage: generate code and run analysis."""
    # Verify lock integrity before analysis
    await verify_lock_integrity(session, paper)

    code_result = await generate_analysis_code(
        session=session,
        paper_id=paper.id,
        provider=provider,
    )

    code_content = code_result.get("code", "")
    if not code_content:
        return {"status": "failed", "reason": "No analysis code generated"}

    exec_result = await execute_analysis(
        session=session,
        paper_id=paper.id,
        code_content=code_content,
        use_container=False,
    )

    return {
        "status": "completed"
        if exec_result.get("success")
        else "completed_with_errors",
        "code_hash": code_result.get("code_hash", ""),
        "code_content": code_content,
        "result_manifest": exec_result,
        "expected_outputs": code_result.get("expected_outputs", []),
    }


async def _stage_drafter(
    session: AsyncSession,
    paper: Paper,
    *,
    result_manifest: dict,
    source_manifest: dict,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Drafter stage: compose manuscript."""
    # Verify lock integrity before drafting
    await verify_lock_integrity(session, paper)

    manuscript_result = await compose_manuscript(
        session=session,
        paper_id=paper.id,
        result_manifest=result_manifest,
        source_manifest=source_manifest,
        provider=provider,
    )

    latex = manuscript_result.get("manuscript_latex", "")
    claims = manuscript_result.get("claims", [])

    return {
        "status": "completed" if latex else "failed",
        "manuscript_latex": latex,
        "claim_count": len(claims),
        "bibliography_count": len(manuscript_result.get("bibliography", [])),
        "inference_level": manuscript_result.get("inference_level", ""),
    }


async def _stage_collegial_review(
    session: AsyncSession,
    paper: Paper,
    *,
    manuscript_latex: str,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Collegial review stage: constructive multi-turn feedback from colleagues."""
    from app.services.collegial.review_loop import run_full_collegial_review
    from app.models.lock_artifact import LockArtifact
    from app.models.claim_map import ClaimMap

    # Load lock YAML for context
    lock_result = await session.execute(
        select(LockArtifact)
        .where(
            LockArtifact.paper_id == paper.id,
            LockArtifact.is_active.is_(True),
        )
        .limit(1)
    )
    lock = lock_result.scalar_one_or_none()
    lock_yaml = lock.lock_yaml if lock else ""

    # Load claims
    claims_result = await session.execute(
        select(ClaimMap).where(ClaimMap.paper_id == paper.id)
    )
    claims = [
        {"claim_text": c.claim_text, "claim_type": c.claim_type}
        for c in claims_result.scalars().all()
    ]

    # Determine target venue from family config if available
    target_venue = None
    if paper.family_id:
        from app.models.paper_family import PaperFamily

        fam_result = await session.execute(
            select(PaperFamily).where(PaperFamily.id == paper.family_id).limit(1)
        )
        family = fam_result.scalar_one_or_none()
        if family and family.venue_ladder_json:
            try:
                venues = json.loads(family.venue_ladder_json)
                flagship = venues.get("flagship", [])
                target_venue = flagship[0] if flagship else None
            except (ValueError, TypeError, IndexError):
                pass

    result = await run_full_collegial_review(
        session=session,
        paper_id=paper.id,
        manuscript_latex=manuscript_latex,
        lock_yaml=lock_yaml,
        claims=claims,
        target_venue=target_venue,
        provider=provider,
    )

    return {
        "status": "completed",
        "session_id": result.get("session_id"),
        "suggestions_accepted": result.get("acknowledgments", [{}])[0].get(
            "accepted_suggestions", 0
        )
        if result.get("acknowledgments")
        else 0,
        "acknowledgments_count": len(result.get("acknowledgments", [])),
        "revised_manuscript": result.get("revised_manuscript"),
        "session_summary": result.get("summary", ""),
    }


async def _stage_verifier(
    session: AsyncSession,
    paper: Paper,
    *,
    result_manifest: dict,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Verifier stage: cross-check claims."""
    # Verify lock integrity before verification
    await verify_lock_integrity(session, paper)

    verification = await verify_manuscript(
        session=session,
        paper_id=paper.id,
        result_manifest=result_manifest,
        provider=provider,
    )

    summary = verification.get("summary", {})

    return {
        "status": "completed",
        "verification": verification,
        "total_claims": summary.get("total_claims", 0),
        "passed_claims": summary.get("passed", 0),
        "failed_claims": summary.get("failed", 0),
        "recommendation": summary.get("recommendation", "unknown"),
    }


async def _stage_packager(
    session: AsyncSession,
    paper: Paper,
    *,
    manuscript_latex: str,
    code_content: str,
    result_manifest: dict,
    source_manifest: dict,
    verification_report: dict,
) -> dict[str, Any]:
    """Packager stage: assemble final package."""
    package = await build_package(
        session=session,
        paper_id=paper.id,
        manuscript_latex=manuscript_latex,
        code_content=code_content,
        result_manifest=result_manifest,
        source_manifest=source_manifest,
        verification_report=verification_report,
    )

    return {
        "status": "completed",
        "merkle_root": package.manifest_hash[:16],
        "version": f"{package.version_major}.{package.version_minor}",
        "package_path": package.package_path,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_stage(
    stage_name: str,
    stage_fn,
    session: AsyncSession,
    paper: Paper,
    **kwargs,
) -> dict[str, Any]:
    """Run a pipeline stage with timing and error handling."""
    start = time.monotonic()
    logger.info("[%s] Starting stage: %s", paper.id, stage_name)

    try:
        result = await stage_fn(session, paper, **kwargs)
    except PipelineViolationError:
        raise  # Let boundary violations propagate
    except Exception as e:
        logger.error(
            "[%s] Stage '%s' failed: %s", paper.id, stage_name, e, exc_info=True
        )
        result = {"status": "failed", "error": str(e)}

    elapsed = time.monotonic() - start
    result["duration_sec"] = round(elapsed, 2)
    result["stage_name"] = stage_name

    logger.info(
        "[%s] Stage '%s' completed in %.1fs (status=%s)",
        paper.id,
        stage_name,
        elapsed,
        result.get("status", "unknown"),
    )
    return result


async def _ensure_paper(session: AsyncSession, paper_id: str, family_id: str) -> Paper:
    """Load or create a Paper record."""
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    paper = result.scalar_one_or_none()

    if paper is not None:
        return paper

    paper = Paper(
        id=paper_id,
        title="Generating...",
        source="ape",
        status="draft",
        review_status="awaiting",
        family_id=family_id,
        funnel_stage="idea",
    )
    session.add(paper)

    # Create initial rating
    rating = Rating(
        paper_id=paper_id,
        mu=settings.trueskill_mu,
        sigma=settings.trueskill_sigma,
        conservative_rating=settings.trueskill_mu - 3 * settings.trueskill_sigma,
        elo=settings.elo_default,
    )
    session.add(rating)
    await session.flush()

    logger.info("Created paper record: %s (family=%s)", paper_id, family_id)
    return paper


async def _reload_paper(session: AsyncSession, paper_id: str) -> Paper:
    """Reload a paper from the database to get current state."""
    # AsyncSession.expire_all() is SYNCHRONOUS — it returns None, not a
    # coroutine. Awaiting it raises ``TypeError: object NoneType can't be
    # used in 'await' expression``. This crashed every pipeline run that
    # made it past Designer (run #25129536542 traceback pointed here).
    session.expire_all()
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    paper = result.scalar_one_or_none()
    if paper is None:
        raise ValueError(f"Paper '{paper_id}' not found during reload.")
    return paper


async def _resolve_family_id(session: AsyncSession, domain_config_id: str) -> str:
    """Resolve a domain_config_id to a family_id.

    Falls back to the first active family if no direct mapping exists.
    """
    # Try direct lookup: some papers already have a family_id
    stmt = select(PaperFamily).where(PaperFamily.active.is_(True)).limit(1)
    result = await session.execute(stmt)
    family = result.scalar_one_or_none()

    if family:
        return family.id

    # Fallback
    return "F1"


async def _set_error(paper_id: str, error: str) -> None:
    """Set error status on a paper (uses its own session)."""
    try:
        async with async_session() as db:
            stmt = (
                update(Paper)
                .where(Paper.id == paper_id)
                .values(
                    status="error",
                    review_status="errors",
                    metadata_json=f'{{"error": "{error[:500]}"}}',
                )
            )
            await db.execute(stmt)
            await db.commit()
    except Exception as e:
        logger.error("Failed to set error on paper %s: %s", paper_id, e)


def _finalise_report(report: dict, pipeline_start: float) -> dict:
    """Add total duration to the pipeline report."""
    report["total_duration_sec"] = round(time.monotonic() - pipeline_start, 2)
    return report
