"""Release state machine: internal -> candidate -> submitted -> public
Each transition has preconditions that must be met."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.paper_package import PaperPackage
from app.models.rating import Rating
from app.models.review import Review
from app.models.significance_memo import SignificanceMemo

logger = logging.getLogger(__name__)

# Valid transitions and their preconditions
RELEASE_TRANSITIONS = {
    ("internal", "candidate"): [
        "all_reviews_passed",
        "package_complete",
        "lock_intact",
        "benchmark_advisory",  # Advisory only — no longer a hard gate
    ],
    ("candidate", "submitted"): [
        "human_signoff",
        "no_unresolved_critical",
        "portfolio_balanced",
        "significance_memo_present",  # Human editorial sign-off required
    ],
    ("submitted", "public"): [
        "submission_confirmed",  # External submission recorded
    ],
    # Reverse transitions (for rejection)
    ("candidate", "internal"): ["rejection_recorded"],
    ("submitted", "internal"): ["rejection_recorded"],
}

# Ordered release statuses for display purposes
RELEASE_STATUSES = ["internal", "candidate", "submitted", "public"]


async def _check_all_reviews_passed(session: AsyncSession, paper: Paper) -> dict:
    """All L1-L4 reviews must have a passing verdict (no 'fail' verdict)."""
    result = await session.execute(
        select(Review)
        .where(Review.paper_id == paper.id)
        .where(Review.stage.in_(["l1_structural", "l2_provenance", "l3_method", "l4_adversarial"]))
    )
    reviews = result.scalars().all()

    if not reviews:
        return {
            "name": "all_reviews_passed",
            "met": False,
            "detail": "No L1-L4 reviews found. All four review layers are required.",
        }

    # Group by stage and check latest iteration for each
    stage_verdicts = {}
    for r in reviews:
        existing = stage_verdicts.get(r.stage)
        if existing is None or r.iteration > existing.iteration:
            stage_verdicts[r.stage] = r

    required_stages = {"l1_structural", "l2_provenance", "l3_method", "l4_adversarial"}
    completed_stages = set(stage_verdicts.keys())
    missing_stages = required_stages - completed_stages

    if missing_stages:
        return {
            "name": "all_reviews_passed",
            "met": False,
            "detail": f"Missing review stages: {', '.join(sorted(missing_stages))}",
        }

    failed_stages = [stage for stage, review in stage_verdicts.items() if review.verdict == "fail"]

    if failed_stages:
        return {
            "name": "all_reviews_passed",
            "met": False,
            "detail": f"Failed review stages: {', '.join(sorted(failed_stages))}",
        }

    return {
        "name": "all_reviews_passed",
        "met": True,
        "detail": "All L1-L4 reviews passed.",
    }


async def _check_package_complete(session: AsyncSession, paper: Paper) -> dict:
    """PaperPackage must exist with a valid manifest hash."""
    result = await session.execute(select(PaperPackage).where(PaperPackage.paper_id == paper.id))
    package = result.scalar_one_or_none()

    if not package:
        return {
            "name": "package_complete",
            "met": False,
            "detail": "No PaperPackage found for this paper.",
        }

    if not package.manifest_hash:
        return {
            "name": "package_complete",
            "met": False,
            "detail": "PaperPackage exists but manifest_hash is empty.",
        }

    return {
        "name": "package_complete",
        "met": True,
        "detail": f"PaperPackage present with manifest hash {package.manifest_hash[:12]}...",
    }


async def _check_lock_intact(session: AsyncSession, paper: Paper) -> dict:
    """Paper lock_hash must be set and match the package lock artifact hash."""
    if not paper.lock_hash:
        return {
            "name": "lock_intact",
            "met": False,
            "detail": "Paper has no lock_hash set.",
        }

    result = await session.execute(select(PaperPackage).where(PaperPackage.paper_id == paper.id))
    package = result.scalar_one_or_none()

    if not package:
        return {
            "name": "lock_intact",
            "met": False,
            "detail": "No PaperPackage to verify lock hash against.",
        }

    if package.lock_artifact_hash and package.lock_artifact_hash != paper.lock_hash:
        if settings.lock_enforcement == "hard":
            return {
                "name": "lock_intact",
                "met": False,
                "detail": (
                    f"Lock hash mismatch: paper={paper.lock_hash[:12]}... "
                    f"vs package={package.lock_artifact_hash[:12]}... "
                    f"(enforcement={settings.lock_enforcement})"
                ),
            }
        else:
            logger.warning(
                "Lock hash mismatch for paper %s (soft enforcement): paper=%s package=%s",
                paper.id,
                paper.lock_hash,
                package.lock_artifact_hash,
            )

    return {
        "name": "lock_intact",
        "met": True,
        "detail": f"Lock hash verified: {paper.lock_hash[:12]}...",
    }


async def _check_benchmark_advisory(session: AsyncSession, paper: Paper) -> dict:
    """Advisory-only tournament check — always passes but provides ranking context.

    Tournament performance is a noisy signal, not a publication verdict.
    The actual submission decision is gated by the significance memo (Phase 2).
    """
    rating_result = await session.execute(select(Rating).where(Rating.paper_id == paper.id))
    rating = rating_result.scalar_one_or_none()

    if rating is None:
        return {
            "name": "benchmark_advisory",
            "met": True,
            "detail": (
                "ADVISORY: No tournament rating found. Paper has not been benchmarked. "
                "Tournament metrics are informational — submission readiness is determined "
                "by the significance memo."
            ),
        }

    ci_lower = (
        rating.confidence_lower
        if rating.confidence_lower is not None
        else rating.mu - 1.96 * rating.sigma
    )
    ci_upper = (
        rating.confidence_upper
        if rating.confidence_upper is not None
        else rating.mu + 1.96 * rating.sigma
    )

    return {
        "name": "benchmark_advisory",
        "met": True,
        "detail": (
            f"ADVISORY: Tournament rank #{rating.rank or 'unranked'}, "
            f"mu={rating.mu:.1f}, sigma={rating.sigma:.1f}, "
            f"conservative={rating.conservative_rating:.1f}, "
            f"95% CI=[{ci_lower:.1f}, {ci_upper:.1f}], "
            f"matches={rating.matches_played}. "
            f"Tournament metrics are noisy signals — submission readiness is "
            f"determined by the significance memo."
        ),
    }


async def _check_significance_memo_present(session: AsyncSession, paper: Paper) -> dict:
    """Check that a significance memo with 'submit' verdict exists.

    The significance memo is a human editorial sign-off that captures why
    this paper is worth submitting, despite tournament results being noisy.
    """
    result = await session.execute(
        select(SignificanceMemo)
        .where(
            SignificanceMemo.paper_id == paper.id,
            SignificanceMemo.editorial_verdict == "submit",
        )
        .order_by(SignificanceMemo.created_at.desc())
        .limit(1)
    )
    memo = result.scalar_one_or_none()

    if memo is None:
        return {
            "name": "significance_memo_present",
            "met": False,
            "detail": (
                "No significance memo with 'submit' verdict found. "
                "A human must write a significance memo explaining why this paper "
                "is ready for submission before it can transition to 'submitted'."
            ),
        }

    return {
        "name": "significance_memo_present",
        "met": True,
        "detail": (
            f"Significance memo present (author: {memo.author}, "
            f"verdict: {memo.editorial_verdict}, "
            f"rank at time: #{memo.tournament_rank_at_time or 'unranked'})."
        ),
    }


async def _check_human_signoff(session: AsyncSession, paper: Paper) -> dict:
    """PaperPackage must have authorship_declaration set (human approved)."""
    result = await session.execute(select(PaperPackage).where(PaperPackage.paper_id == paper.id))
    package = result.scalar_one_or_none()

    if not package or not package.authorship_declaration:
        return {
            "name": "human_signoff",
            "met": False,
            "detail": "No authorship declaration found. Human sign-off required.",
        }

    return {
        "name": "human_signoff",
        "met": True,
        "detail": "Authorship declaration present.",
    }


async def _check_no_unresolved_critical(session: AsyncSession, paper: Paper) -> dict:
    """No critical severity issues with open status."""
    result = await session.execute(
        select(func.count())
        .select_from(Review)
        .where(Review.paper_id == paper.id)
        .where(Review.severity == "critical")
        .where(Review.resolution_status == "open")
    )
    count = result.scalar() or 0

    if count > 0:
        return {
            "name": "no_unresolved_critical",
            "met": False,
            "detail": f"{count} unresolved critical issue(s) remain.",
        }

    return {
        "name": "no_unresolved_critical",
        "met": True,
        "detail": "No unresolved critical issues.",
    }


async def _check_portfolio_balanced(session: AsyncSession, paper: Paper) -> dict:
    """Family must not exceed its max_portfolio_share of total submitted/public papers."""
    if not paper.family_id:
        return {
            "name": "portfolio_balanced",
            "met": True,
            "detail": "Paper has no family; portfolio balance check not applicable.",
        }

    # Get family max_portfolio_share
    family_result = await session.execute(
        select(PaperFamily).where(PaperFamily.id == paper.family_id)
    )
    family = family_result.scalar_one_or_none()
    max_share = family.max_portfolio_share if family else 0.33

    # Count total papers in submitted or public release status
    total_result = await session.execute(
        select(func.count())
        .select_from(Paper)
        .where(Paper.release_status.in_(["submitted", "public"]))
    )
    total_released = (total_result.scalar() or 0) + 1  # +1 for this paper if it transitions

    # Count papers in same family that are submitted or public
    family_result = await session.execute(
        select(func.count())
        .select_from(Paper)
        .where(Paper.family_id == paper.family_id)
        .where(Paper.release_status.in_(["submitted", "public"]))
        .where(Paper.id != paper.id)  # exclude self
    )
    family_count = (family_result.scalar() or 0) + 1  # +1 for this paper

    if total_released == 0:
        current_share = 0.0
    else:
        current_share = family_count / total_released

    if current_share > max_share:
        return {
            "name": "portfolio_balanced",
            "met": False,
            "detail": (
                f"Family '{paper.family_id}' would hold {current_share:.1%} of released papers "
                f"({family_count}/{total_released}), exceeding max share of {max_share:.1%}."
            ),
        }

    return {
        "name": "portfolio_balanced",
        "met": True,
        "detail": (
            f"Family '{paper.family_id}' at {current_share:.1%} "
            f"({family_count}/{total_released}), within max share of {max_share:.1%}."
        ),
    }


async def _check_submission_confirmed(session: AsyncSession, paper: Paper) -> dict:
    """Paper must have funnel_stage 'submitted' or 'public' to confirm external submission."""
    if paper.funnel_stage in ("submitted", "public"):
        return {
            "name": "submission_confirmed",
            "met": True,
            "detail": f"External submission confirmed (funnel_stage='{paper.funnel_stage}').",
        }

    return {
        "name": "submission_confirmed",
        "met": False,
        "detail": f"Funnel stage is '{paper.funnel_stage}'; needs 'submitted' or 'public'.",
    }


async def _check_rejection_recorded(session: AsyncSession, paper: Paper) -> dict:
    """Always met -- rejection just requires an admin action (force or approved_by)."""
    return {
        "name": "rejection_recorded",
        "met": True,
        "detail": "Rejection transitions are always available.",
    }


# Map precondition names to checker functions
_PRECONDITION_CHECKERS = {
    "all_reviews_passed": _check_all_reviews_passed,
    "package_complete": _check_package_complete,
    "lock_intact": _check_lock_intact,
    "benchmark_advisory": _check_benchmark_advisory,
    "human_signoff": _check_human_signoff,
    "no_unresolved_critical": _check_no_unresolved_critical,
    "portfolio_balanced": _check_portfolio_balanced,
    "significance_memo_present": _check_significance_memo_present,
    "submission_confirmed": _check_submission_confirmed,
    "rejection_recorded": _check_rejection_recorded,
}


async def check_transition_preconditions(
    session: AsyncSession,
    paper_id: str,
    target_status: str,
) -> dict:
    """Check if a paper can transition to the target release status.

    Returns {
        "can_transition": bool,
        "current_status": str,
        "target_status": str,
        "preconditions": [
            {"name": str, "met": bool, "detail": str}
        ],
        "blockers": [str]  # names of unmet preconditions
    }
    """
    result = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        return {
            "can_transition": False,
            "current_status": None,
            "target_status": target_status,
            "preconditions": [],
            "blockers": ["paper_not_found"],
        }

    current_status = paper.release_status
    transition_key = (current_status, target_status)

    if transition_key not in RELEASE_TRANSITIONS:
        return {
            "can_transition": False,
            "current_status": current_status,
            "target_status": target_status,
            "preconditions": [],
            "blockers": [
                f"Invalid transition: '{current_status}' -> '{target_status}'. "
                f"Valid targets from '{current_status}': "
                f"{[t for (f, t) in RELEASE_TRANSITIONS if f == current_status]}"
            ],
        }

    precondition_names = RELEASE_TRANSITIONS[transition_key]
    preconditions = []

    for name in precondition_names:
        checker = _PRECONDITION_CHECKERS.get(name)
        if checker:
            result_item = await checker(session, paper)
            preconditions.append(result_item)
        else:
            preconditions.append(
                {
                    "name": name,
                    "met": False,
                    "detail": f"Unknown precondition checker: {name}",
                }
            )

    blockers = [p["name"] for p in preconditions if not p["met"]]

    return {
        "can_transition": len(blockers) == 0,
        "current_status": current_status,
        "target_status": target_status,
        "preconditions": preconditions,
        "blockers": blockers,
    }


async def transition_release_status(
    session: AsyncSession,
    paper_id: str,
    target_status: str,
    force: bool = False,
    approved_by: str | None = None,
) -> dict:
    """Transition a paper's release status.

    If force=False (default), all preconditions must be met.
    If force=True, only logs a warning but proceeds (for admin override).

    Returns transition result with before/after status.
    """
    check = await check_transition_preconditions(session, paper_id, target_status)

    if not check["can_transition"] and not force:
        return {
            "success": False,
            "paper_id": paper_id,
            "before": check["current_status"],
            "after": check["current_status"],
            "target": target_status,
            "blockers": check["blockers"],
            "preconditions": check["preconditions"],
            "message": "Transition blocked by unmet preconditions.",
        }

    if not check["can_transition"] and force:
        logger.warning(
            "Force-transitioning paper %s from '%s' to '%s' despite blockers: %s (approved_by=%s)",
            paper_id,
            check["current_status"],
            target_status,
            check["blockers"],
            approved_by,
        )

    # Perform the transition
    before_status = check["current_status"]
    now = datetime.now(UTC)

    await session.execute(
        update(Paper)
        .where(Paper.id == paper_id)
        .values(
            release_status=target_status,
            updated_at=now,
        )
    )

    # Also update funnel_stage to match if moving forward in the release pipeline
    funnel_update_map = {
        "candidate": "candidate",
        "submitted": "submitted",
        "public": "public",
    }
    if target_status in funnel_update_map:
        await session.execute(
            update(Paper)
            .where(Paper.id == paper_id)
            .values(funnel_stage=funnel_update_map[target_status])
        )

    await session.commit()

    logger.info(
        "Paper %s transitioned: %s -> %s (force=%s, approved_by=%s)",
        paper_id,
        before_status,
        target_status,
        force,
        approved_by,
    )

    return {
        "success": True,
        "paper_id": paper_id,
        "before": before_status,
        "after": target_status,
        "forced": force,
        "approved_by": approved_by,
        "preconditions": check["preconditions"],
        "message": f"Transitioned from '{before_status}' to '{target_status}'.",
    }


async def get_release_pipeline_status(
    session: AsyncSession,
    family_id: str | None = None,
) -> dict:
    """Get overview of papers in each release status.
    Optionally filtered by family.
    Returns counts and lists of papers per status.
    """
    query = select(Paper)
    if family_id:
        query = query.where(Paper.family_id == family_id)

    result = await session.execute(query)
    papers = result.scalars().all()

    pipeline = {status: [] for status in RELEASE_STATUSES}
    for paper in papers:
        status = paper.release_status
        if status in pipeline:
            pipeline[status].append(
                {
                    "id": paper.id,
                    "title": paper.title,
                    "family_id": paper.family_id,
                    "funnel_stage": paper.funnel_stage,
                    "updated_at": paper.updated_at.isoformat() if paper.updated_at else None,
                }
            )

    counts = {status: len(items) for status, items in pipeline.items()}

    return {
        "family_id": family_id,
        "counts": counts,
        "total": sum(counts.values()),
        "pipeline": pipeline,
    }
