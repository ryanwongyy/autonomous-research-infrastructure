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
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider
from app.services.paper_generation.boundary_enforcer import (
    PipelineViolationError,
    verify_lock_integrity,
)
from app.services.paper_generation.roles.analyst import execute_analysis, generate_analysis_code
from app.services.paper_generation.roles.data_steward import (
    build_source_manifest,
    fetch_and_snapshot,
)
from app.services.paper_generation.roles.designer import create_research_design, lock_design
from app.services.paper_generation.roles.drafter import compose_manuscript
from app.services.paper_generation.roles.packager import build_package
from app.services.paper_generation.roles.scout import generate_ideas, screen_idea
from app.services.paper_generation.roles.verifier import verify_manuscript

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


async def run_full_pipeline(
    session: AsyncSession,
    family_id: str,
    paper_id: str | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Run the complete paper generation pipeline.

    Each stage:
    1. Verifies preconditions (previous stage completed, lock intact)
    2. Executes the role
    3. Updates Paper.funnel_stage
    4. Verifies lock hasn't been tampered with (for stages after lock)

    Returns pipeline report with timing, status per stage, and final paper_id.
    """
    pipeline_start = time.monotonic()

    # Resolve provider once for all roles (model is selected per-role downstream)
    if provider is None:
        provider, _model = await get_generation_provider()

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
        paper = await _ensure_paper(session, paper_id, family_id)

        # ---------------------------------------------------------------
        # 1. SCOUT: generate and screen ideas
        # ---------------------------------------------------------------
        stage_report = await _run_stage(
            "scout",
            _stage_scout,
            session,
            paper,
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
        stage_report = await _run_stage(
            "designer",
            _stage_designer,
            session,
            paper,
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
        # Re-load paper to get updated funnel_stage after lock
        paper = await _reload_paper(session, paper_id)
        stage_report = await _run_stage(
            "data_steward",
            _stage_data_steward,
            session,
            paper,
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
        paper = await _reload_paper(session, paper_id)
        stage_report = await _run_stage(
            "analyst",
            _stage_analyst,
            session,
            paper,
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
        paper = await _reload_paper(session, paper_id)
        stage_report = await _run_stage(
            "drafter",
            _stage_drafter,
            session,
            paper,
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
        paper = await _reload_paper(session, paper_id)
        stage_report = await _run_stage(
            "collegial_review",
            _stage_collegial_review,
            session,
            paper,
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
        paper = await _reload_paper(session, paper_id)
        stage_report = await _run_stage(
            "verifier",
            _stage_verifier,
            session,
            paper,
            result_manifest=result_manifest,
            provider=provider,
        )
        report["stages"]["verifier"] = stage_report

        verification_report = stage_report.get("verification", {})
        recommendation = verification_report.get("summary", {}).get("recommendation", "revise")

        # If verifier recommends rejection, kill the paper
        if recommendation == "reject":
            paper = await _reload_paper(session, paper_id)
            paper.funnel_stage = "killed"
            paper.kill_reason = "Verifier recommended rejection"
            session.add(paper)
            await session.flush()
            report["final_status"] = "rejected_by_verifier"
            return _finalise_report(report, pipeline_start)

        # ---------------------------------------------------------------
        # 7. PACKAGER: assemble final package
        # ---------------------------------------------------------------
        paper = await _reload_paper(session, paper_id)
        stage_report = await _run_stage(
            "packager",
            _stage_packager,
            session,
            paper,
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
        paper = await _reload_paper(session, paper_id)
        report["final_status"] = f"completed (funnel_stage={paper.funnel_stage})"

        await session.commit()
        logger.info("Pipeline completed for paper %s", paper_id)

    except PipelineViolationError as e:
        report["final_status"] = f"boundary_violation: {e}"
        logger.error("Pipeline boundary violation for paper %s: %s", paper_id, e)
        await session.rollback()
    except Exception as e:
        report["final_status"] = f"error: {e}"
        logger.error("Pipeline failed for paper %s: %s", paper_id, e, exc_info=True)
        await session.rollback()
        await _set_error(paper_id, str(e))

    return _finalise_report(report, pipeline_start)


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
        screening_results.append(
            {
                "question": idea.get("research_question", "")[:80],
                "composite": screening.get("weighted_composite", 0),
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
    """Data Steward stage: build manifest and fetch data."""
    source_manifest = await build_source_manifest(
        session=session,
        paper_id=paper.id,
        provider=provider,
    )

    # Fetch and snapshot each source
    snapshots_created = 0
    fetch_errors: list[str] = []

    for source_entry in source_manifest.get("sources", []):
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

    return {
        "status": "completed" if snapshots_created > 0 else "failed",
        "source_manifest": source_manifest,
        "snapshots_created": snapshots_created,
        "fetch_errors": fetch_errors,
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
        "status": "completed" if exec_result.get("success") else "completed_with_errors",
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
    from app.models.claim_map import ClaimMap
    from app.models.lock_artifact import LockArtifact
    from app.services.collegial.review_loop import run_full_collegial_review

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
    claims_result = await session.execute(select(ClaimMap).where(ClaimMap.paper_id == paper.id))
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
        logger.error("[%s] Stage '%s' failed: %s", paper.id, stage_name, e, exc_info=True)
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
    await session.expire_all()
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
