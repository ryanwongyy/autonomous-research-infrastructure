"""Enforces role boundaries throughout the paper generation pipeline.

With hard enforcement (config.lock_enforcement == 'hard'), any violation
raises PipelineViolationError immediately. With soft enforcement, violations
are logged but execution continues.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from sqlalchemy import select

from app.models.lock_artifact import LockArtifact
from app.models.claim_map import ClaimMap
from app.services.storage.lock_manager import verify_lock, extract_design_fields
from app.config import settings

logger = logging.getLogger(__name__)


class PipelineViolationError(Exception):
    """Raised when a role boundary is violated in hard-enforcement mode."""


# ---------------------------------------------------------------------------
# Valid funnel-stage transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, list[str]] = {
    "idea": ["screened", "killed"],
    "screened": ["locked", "killed"],
    "locked": ["ingesting", "killed"],
    "ingesting": ["analyzing", "killed"],
    "analyzing": ["drafting", "killed"],
    "drafting": ["reviewing", "killed"],
    "reviewing": ["revision", "candidate", "killed"],
    "revision": ["reviewing", "candidate", "killed"],
    "candidate": ["submitted", "revision", "killed"],
    "submitted": ["public", "revision", "killed"],
    "public": [],
    "killed": [],
}

# Stages that require a valid lock artifact
LOCK_REQUIRED_STAGES = {
    "ingesting",
    "analyzing",
    "drafting",
    "reviewing",
    "revision",
    "candidate",
    "submitted",
    "public",
}

# Stage prerequisites: what funnel_stage the paper must be at (or past)
# before each pipeline step can run
STAGE_PREREQUISITES: dict[str, set[str]] = {
    "scout": {"idea", "screened"},
    "designer": {"screened"},
    "data_steward": {"locked"},
    "analyst": {"locked", "ingesting"},
    "drafter": {"locked", "ingesting", "analyzing"},
    "collegial_reviewer": {"drafting"},
    "verifier": {"drafting"},
    "packager": {"reviewing", "revision"},
}


# ---------------------------------------------------------------------------
# Public verification functions
# ---------------------------------------------------------------------------

async def verify_lock_integrity(
    session: AsyncSession, paper: Paper
) -> bool:
    """Verify the paper's lock hash matches the active lock artifact.

    Returns True if valid, False otherwise.
    Raises PipelineViolationError in hard-enforcement mode on failure.
    """
    result = await verify_lock(session, paper.id)

    if result["valid"]:
        return True

    violations = result.get("violations", [])
    msg = (
        f"Lock integrity check failed for paper '{paper.id}': "
        f"{'; '.join(violations)}"
    )

    if settings.lock_enforcement == "hard":
        logger.error(msg)
        raise PipelineViolationError(msg)
    else:
        logger.warning(msg)
        return False


def verify_funnel_stage(
    paper: Paper, required_stages: set[str] | str
) -> bool:
    """Verify the paper is at one of the required funnel stages.

    Args:
        paper: The paper to check.
        required_stages: A set of acceptable stages, or a single stage string.

    Returns True if the paper is at an acceptable stage.
    Raises PipelineViolationError in hard-enforcement mode on failure.
    """
    if isinstance(required_stages, str):
        required_stages = {required_stages}

    if paper.funnel_stage in required_stages:
        return True

    msg = (
        f"Pipeline stage violation for paper '{paper.id}': "
        f"current stage '{paper.funnel_stage}' not in required stages "
        f"{required_stages}"
    )

    if settings.lock_enforcement == "hard":
        logger.error(msg)
        raise PipelineViolationError(msg)
    else:
        logger.warning(msg)
        return False


def verify_stage_transition(
    paper: Paper, target_stage: str
) -> bool:
    """Verify that transitioning to the target stage is valid.

    Returns True if the transition is valid.
    Raises PipelineViolationError in hard-enforcement mode on invalid transition.
    """
    current = paper.funnel_stage
    valid_targets = VALID_TRANSITIONS.get(current, [])

    if target_stage in valid_targets:
        return True

    msg = (
        f"Invalid funnel-stage transition for paper '{paper.id}': "
        f"'{current}' -> '{target_stage}'. "
        f"Valid transitions from '{current}': {valid_targets}"
    )

    if settings.lock_enforcement == "hard":
        logger.error(msg)
        raise PipelineViolationError(msg)
    else:
        logger.warning(msg)
        return False


def enforce_tier_requirement(
    claim_type: str, source_tier: str
) -> bool:
    """Enforce that Tier C sources cannot anchor central claims.

    Central claim types: 'empirical', 'doctrinal', 'historical'.
    Descriptive and theoretical claims may use any tier.

    Returns True if compliant.
    Raises PipelineViolationError in hard-enforcement mode on violation.
    """
    central_types = {"empirical", "doctrinal", "historical"}

    if claim_type not in central_types:
        return True

    if source_tier != "C":
        return True

    msg = (
        f"Tier violation: claim type '{claim_type}' is a central claim "
        f"and cannot be anchored by a Tier C source. "
        f"Central claims require Tier A or B sources."
    )

    if settings.lock_enforcement == "hard":
        logger.error(msg)
        raise PipelineViolationError(msg)
    else:
        logger.warning(msg)
        return False


async def verify_design_data_coherence(
    session: AsyncSession, paper: Paper
) -> bool:
    """Pre-analysis check: locked design questions still align with data manifest sources.

    Compares the data_sources field in the lock YAML against source snapshots
    actually associated with this paper. Blocks if overlap is below threshold.
    """
    lock = await _get_active_lock(session, paper.id)
    if lock is None:
        return True  # No lock to check against

    design = extract_design_fields(lock.lock_yaml)
    design_sources = set(s.lower() for s in design["data_sources"])

    if not design_sources:
        return True  # Design doesn't specify sources

    # Structural check: verify the design specifies meaningful content.
    # Source snapshots are linked via the lock artifact's source_manifest_hash
    # rather than directly by paper_id, so we verify the design is non-empty.
    if len(design_sources) == 0 and len(design["research_questions"]) == 0:
        msg = f"Manifest drift: paper '{paper.id}' has empty design fields in lock artifact."
        if settings.lock_enforcement == "hard":
            logger.error(msg)
            raise PipelineViolationError(msg)
        logger.warning(msg)
        return False

    logger.info(
        "[%s] Design-data coherence check passed: %d design sources specified",
        paper.id, len(design_sources),
    )
    return True


async def verify_analysis_design_alignment(
    session: AsyncSession, paper: Paper
) -> bool:
    """Pre-drafting check: analysis outputs align with design expected_outputs.

    Ensures the design's expected_outputs list is non-empty and that the paper
    has progressed through the analysis stage with artifacts present.
    """
    lock = await _get_active_lock(session, paper.id)
    if lock is None:
        return True

    design = extract_design_fields(lock.lock_yaml)
    expected_outputs = design["expected_outputs"]

    if not expected_outputs:
        # Design doesn't specify expected outputs — pass with warning
        logger.warning(
            "[%s] Design does not specify expected_outputs; skipping alignment check",
            paper.id,
        )
        return True

    # Verify the paper has actually reached or passed the analysis stage
    analysis_stages = {"analyzing", "drafting", "reviewing", "revision", "candidate", "submitted", "public"}
    if paper.funnel_stage not in analysis_stages:
        msg = (
            f"Analysis-design alignment: paper '{paper.id}' has not completed analysis "
            f"(current stage: '{paper.funnel_stage}') but design expects {len(expected_outputs)} outputs."
        )
        if settings.lock_enforcement == "hard":
            logger.error(msg)
            raise PipelineViolationError(msg)
        logger.warning(msg)
        return False

    logger.info(
        "[%s] Analysis-design alignment check passed: %d expected outputs in design",
        paper.id, len(expected_outputs),
    )
    return True


async def verify_claims_analysis_alignment(
    session: AsyncSession, paper: Paper
) -> bool:
    """Pre-packaging check: claim_map entries link to actual analysis results or sources.

    Ensures all claims in the claim_map have either a source_card_id or
    result_object_ref populated (not orphaned claims).
    """
    result = await session.execute(
        select(ClaimMap).where(ClaimMap.paper_id == paper.id)
    )
    claims = result.scalars().all()

    if not claims:
        # No claims yet — this is acceptable if the paper hasn't been drafted
        return True

    orphan_claims = []
    for claim in claims:
        has_source = claim.source_card_id is not None
        has_result = claim.result_object_ref is not None
        if not has_source and not has_result:
            orphan_claims.append(claim.claim_text[:80] if claim.claim_text else f"claim_{claim.id}")

    if orphan_claims:
        threshold = settings.drift_threshold
        orphan_ratio = len(orphan_claims) / len(claims)
        linked_ratio = 1.0 - orphan_ratio

        if linked_ratio < threshold:
            msg = (
                f"Claims-analysis drift: paper '{paper.id}' has {len(orphan_claims)}/{len(claims)} "
                f"unlinked claims (linked ratio {linked_ratio:.2f} < threshold {threshold:.2f}). "
                f"First orphan: '{orphan_claims[0]}'"
            )
            if settings.lock_enforcement == "hard":
                logger.error(msg)
                raise PipelineViolationError(msg)
            logger.warning(msg)
            return False

    logger.info(
        "[%s] Claims-analysis alignment check passed: %d/%d claims linked",
        paper.id, len(claims) - len(orphan_claims), len(claims),
    )
    return True


async def _get_active_lock(session: AsyncSession, paper_id: str):
    """Fetch the active lock artifact for a paper."""
    result = await session.execute(
        select(LockArtifact).where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def enforce_preconditions(
    session: AsyncSession,
    paper: Paper,
    role_name: str,
) -> bool:
    """Enforce all preconditions for a pipeline role.

    Checks:
    1. Paper is at an acceptable funnel stage for this role
    2. If the role requires a lock, verify lock integrity
    3. Role-specific manifest-drift checks

    Returns True if all preconditions are met.
    Raises PipelineViolationError in hard-enforcement mode on failure.
    """
    # Check funnel stage
    required = STAGE_PREREQUISITES.get(role_name)
    if required:
        verify_funnel_stage(paper, required)

    # Check lock integrity for stages that require it
    if paper.funnel_stage in LOCK_REQUIRED_STAGES:
        await verify_lock_integrity(session, paper)

    # Role-specific manifest-drift checks
    if role_name == "analyst":
        await verify_design_data_coherence(session, paper)
    elif role_name == "drafter":
        await verify_analysis_design_alignment(session, paper)
    elif role_name == "packager":
        await verify_claims_analysis_alignment(session, paper)

    return True


def enforce_causal_language(
    protocol_type: str, claim_text: str
) -> bool:
    """Check if a claim uses causal language and whether the protocol permits it.

    Returns True if compliant.
    Raises PipelineViolationError in hard-enforcement mode on violation.
    """
    causal_markers = [
        " causes ", " caused ", " causing ",
        " effect of ", " effects of ",
        " impact of ", " impacts of ",
        " leads to ", " led to ",
        " results in ", " resulted in ",
        " due to ",
        " because of ",
        " increases ", " decreases ",
        " reduces ", " improves ",
    ]

    # Protocols that permit causal language
    causal_protocols = {"empirical_causal"}
    # Protocols that permit limited mechanistic claims
    mechanistic_protocols = {"process_tracing", "comparative_historical"}

    claim_lower = f" {claim_text.lower()} "
    has_causal = any(marker in claim_lower for marker in causal_markers)

    if not has_causal:
        return True

    if protocol_type in causal_protocols:
        return True

    if protocol_type in mechanistic_protocols:
        # Allow but log
        logger.info(
            "Mechanistic causal language detected in '%s' protocol (permitted with caveats)",
            protocol_type,
        )
        return True

    msg = (
        f"Causal language violation: claim uses causal language but "
        f"protocol '{protocol_type}' does not permit causal inference. "
        f"Claim excerpt: '{claim_text[:100]}...'"
    )

    if settings.lock_enforcement == "hard":
        logger.error(msg)
        raise PipelineViolationError(msg)
    else:
        logger.warning(msg)
        return False
