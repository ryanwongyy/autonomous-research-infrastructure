"""Tier 1a: Analyzes role-level failure patterns and proposes prompt patches."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failure_record import FailureRecord
from app.models.paper import Paper
from app.models.prompt_version import PromptVersion
from app.models.review import Review
from app.models.rsi_experiment import RSIExperiment
from app.services.rsi.experiment_manager import create_experiment
from app.services.rsi.prompt_registry import get_active_prompt, register_prompt
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# Map pipeline roles to the detection stages recorded in failure records.
ROLE_STAGE_MAP: dict[str, str] = {
    "scout": "screening",
    "designer": "design",
    "data_steward": "ingestion",
    "analyst": "analysis",
    "drafter": "drafting",
    "verifier": "verification",
    "packager": "packaging",
}

# Pre-authored patch fragments keyed by failure_type.  These are deterministic
# (no LLM call) -- the optimizer simply appends the relevant patches to the
# current prompt when a failure type dominates.
FAILURE_PATCHES: dict[str, str] = {
    "hallucination": (
        "\n\nCRITICAL: Every factual claim MUST cite a specific source. "
        "Never generate data, statistics, or findings that are not directly "
        "traceable to an ingested source card."
    ),
    "causal_overreach": (
        "\n\nCAUTION: Do NOT use causal language (causes, leads to, impacts, "
        "results in) unless the research design explicitly supports causal "
        "inference. Use associational language (correlates with, is associated "
        "with) as the default."
    ),
    "data_error": (
        "\n\nDATA INTEGRITY: Verify all data references against the source "
        "manifest before use. Flag any data that appears stale (>90 days), "
        "incomplete, or inconsistent with the source card's documented schema."
    ),
    "source_drift": (
        "\n\nSOURCE BOUNDARIES: Each source card has explicit claim permissions "
        "and prohibitions. Before making any claim, verify it falls within the "
        "source's permission profile. Never extrapolate beyond what the source "
        "authorizes."
    ),
    "logic_error": (
        "\n\nLOGICAL RIGOR: Check all logical chains for validity. Ensure "
        "conclusions follow from premises. Flag any logical gaps, non-sequiturs, "
        "or circular reasoning."
    ),
    "design_violation": (
        "\n\nDESIGN ADHERENCE: Your output MUST conform to the locked design "
        "specification. Do not deviate from the research questions, methods, "
        "or expected outputs defined in the lock artifact."
    ),
    "formatting": (
        "\n\nFORMATTING: Follow the target venue's formatting requirements "
        "exactly. Check section structure, citation format, word limits, and "
        "style conventions before finalizing."
    ),
}

# How many top failure patterns to include in a patch proposal.
_MAX_PATCH_PATTERNS = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_role_failures(
    session: AsyncSession,
    role_name: str,
    family_id: str | None = None,
    lookback_days: int = 90,
) -> dict:
    """Analyze failure patterns for a specific pipeline role.

    Returns a structured analysis including failure counts by type and
    severity, the top recurring patterns, and the first-pass rate of
    reviews at the corresponding stage.
    """
    role_name = role_name.lower()
    if role_name not in ROLE_STAGE_MAP:
        raise ValueError(
            f"Unknown role '{role_name}'. Must be one of: "
            f"{', '.join(sorted(ROLE_STAGE_MAP))}"
        )

    detection_stage = ROLE_STAGE_MAP[role_name]
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    # ------------------------------------------------------------------
    # 1. Query failure records for this detection stage
    # ------------------------------------------------------------------
    failure_filters = [
        FailureRecord.detection_stage == detection_stage,
        FailureRecord.created_at >= cutoff,
    ]
    if family_id is not None:
        failure_filters.append(FailureRecord.family_id == family_id)

    failure_result = await session.execute(
        select(FailureRecord).where(and_(*failure_filters))
    )
    failures = failure_result.scalars().all()

    total_failures = len(failures)
    by_type: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()
    # Track (type, severity) combos and keep one example per combo.
    combo_examples: dict[tuple[str, str], str] = {}
    for f in failures:
        by_type[f.failure_type] += 1
        by_severity[f.severity] += 1
        key = (f.failure_type, f.severity)
        if key not in combo_examples:
            example = f.resolution or f.corrective_action or f.root_cause_category or ""
            combo_examples[key] = example[:300]  # truncate long text

    # ------------------------------------------------------------------
    # 2. Build top_patterns (ordered by count desc)
    # ------------------------------------------------------------------
    combo_counts: Counter[tuple[str, str]] = Counter()
    for f in failures:
        combo_counts[(f.failure_type, f.severity)] += 1

    top_patterns = [
        {
            "type": ftype,
            "severity": sev,
            "count": count,
            "example_text": combo_examples.get((ftype, sev), ""),
        }
        for (ftype, sev), count in combo_counts.most_common(10)
    ]

    # ------------------------------------------------------------------
    # 3. Compute first-pass rate from Review table
    # ------------------------------------------------------------------
    # Reviews at the matching *review stage* (detection_stage doubles as the
    # review layer label in many cases, but the Review.stage column uses the
    # l1_structural / l2_provenance / etc. taxonomy).  We approximate by
    # counting all reviews whose iteration==1 and checking pass/fail.
    review_filters = [
        Review.iteration == 1,
        Review.created_at >= cutoff,
    ]
    # If the detection_stage looks like an "l*_..." layer name, match
    # directly; otherwise match any review whose paper belongs to the role's
    # detection_stage via the Paper.funnel_stage column.
    if detection_stage.startswith("l"):
        review_filters.append(Review.stage == detection_stage)
    else:
        # Join through Paper to match funnel_stage
        review_filters.append(Paper.funnel_stage == detection_stage)

    if family_id is not None:
        review_filters.append(Review.family_id == family_id)

    if detection_stage.startswith("l"):
        first_pass_query = (
            select(
                func.count().label("total"),
                func.count().filter(Review.verdict == "pass").label("passed"),
            )
            .where(and_(*review_filters))
        )
    else:
        first_pass_query = (
            select(
                func.count().label("total"),
                func.count().filter(Review.verdict == "pass").label("passed"),
            )
            .select_from(Review)
            .join(Paper, Paper.id == Review.paper_id)
            .where(and_(*review_filters))
        )

    fpr_result = await session.execute(first_pass_query)
    row = fpr_result.one()
    total_reviews = row.total or 0
    passed_reviews = row.passed or 0
    first_pass_rate = (passed_reviews / total_reviews) if total_reviews > 0 else 0.0

    return {
        "role": role_name,
        "detection_stage": detection_stage,
        "lookback_days": lookback_days,
        "total_failures": total_failures,
        "by_type": dict(by_type),
        "by_severity": dict(by_severity),
        "top_patterns": top_patterns,
        "first_pass_rate": round(first_pass_rate, 4),
        "total_reviews_sampled": total_reviews,
    }


async def propose_prompt_patch(
    session: AsyncSession,
    role_name: str,
    failure_analysis: dict,
    current_prompt: str | None = None,
) -> dict:
    """Propose a prompt patch based on failure analysis.

    Does NOT call an LLM.  Instead, it deterministically selects pre-authored
    patch fragments matching the top failure types from ``failure_analysis``
    and appends them to the current prompt.  An RSI experiment and a new
    prompt version are created in ``proposed`` status.
    """
    role_name = role_name.lower()

    # Resolve current prompt from the registry if not provided.
    if current_prompt is None:
        current_prompt = await get_active_prompt(session, "role_prompt", role_name)
    if current_prompt is None:
        current_prompt = f"You are the {role_name} agent in the APE pipeline."

    # Determine which failure types to target (top N from analysis).
    top_patterns = failure_analysis.get("top_patterns", [])
    targeted_types: list[str] = []
    seen: set[str] = set()
    for pat in top_patterns:
        ftype = pat.get("type", "")
        if ftype in FAILURE_PATCHES and ftype not in seen:
            targeted_types.append(ftype)
            seen.add(ftype)
        if len(targeted_types) >= _MAX_PATCH_PATTERNS:
            break

    if not targeted_types:
        return {
            "experiment_id": None,
            "prompt_version_id": None,
            "patch_summary": "No actionable failure patterns found; no patch proposed.",
            "targeted_failures": [],
        }

    # Build the patched prompt text.
    patch_additions = "".join(FAILURE_PATCHES[ft] for ft in targeted_types)
    patched_text = current_prompt + patch_additions

    # Create experiment.
    total_failures = failure_analysis.get("total_failures", 0)
    exp_name = (
        f"role_prompt_patch_{role_name}_"
        f"{'_'.join(targeted_types[:2])}_n{total_failures}"
    )
    experiment = await create_experiment(
        session,
        tier="1a",
        name=exp_name,
        config_snapshot={
            "role": role_name,
            "targeted_failures": targeted_types,
            "failure_analysis_summary": {
                "total_failures": total_failures,
                "first_pass_rate": failure_analysis.get("first_pass_rate"),
            },
        },
    )

    # Register new prompt version.
    prompt_version = await register_prompt(
        session,
        target_type="role_prompt",
        target_key=role_name,
        prompt_text=patched_text,
        experiment_id=experiment.id,
    )

    patch_summary = (
        f"Proposed patch for role '{role_name}' targeting "
        f"{', '.join(targeted_types)} failures "
        f"(total failures in window: {total_failures})."
    )
    logger.info("Tier 1a patch proposed: %s", patch_summary)

    return {
        "experiment_id": experiment.id,
        "prompt_version_id": prompt_version.id,
        "patch_summary": patch_summary,
        "targeted_failures": targeted_types,
    }


async def evaluate_prompt_patch(
    session: AsyncSession,
    experiment_id: int,
    lookback_days: int = 30,
) -> dict:
    """Evaluate a prompt patch by comparing failure rates before/after activation.

    Loads the experiment, determines its activation date, then compares
    failure counts in equally-sized windows before and after that date.
    """
    # Load experiment.
    exp_result = await session.execute(
        select(RSIExperiment).where(RSIExperiment.id == experiment_id)
    )
    experiment = exp_result.scalar_one_or_none()
    if experiment is None:
        raise ValueError(f"Experiment {experiment_id} not found")

    # Determine the activation date.
    activation_date = experiment.activated_at
    if activation_date is None:
        return {
            "decision": "hold",
            "reason": "Experiment has not been activated yet.",
            "before": {},
            "after": {},
            "improvement_pct": 0.0,
        }

    # Derive role name and detection_stage from config snapshot.
    config = safe_json_loads(experiment.config_snapshot_json, {})
    role_name = config.get("role")
    if role_name is None or role_name not in ROLE_STAGE_MAP:
        raise ValueError(
            f"Experiment {experiment_id} config missing valid 'role'. "
            f"Found: {role_name}"
        )
    detection_stage = ROLE_STAGE_MAP[role_name]

    window = timedelta(days=lookback_days)
    before_start = activation_date - window
    after_end = activation_date + window

    # Helper: count failures in a date range for this stage.
    async def _count_failures(start: datetime, end: datetime) -> dict:
        result = await session.execute(
            select(
                FailureRecord.failure_type,
                func.count().label("cnt"),
            )
            .where(
                FailureRecord.detection_stage == detection_stage,
                FailureRecord.created_at >= start,
                FailureRecord.created_at < end,
            )
            .group_by(FailureRecord.failure_type)
        )
        rows = result.all()
        by_type = {row.failure_type: row.cnt for row in rows}
        total = sum(by_type.values())
        return {"failure_rate": total, "by_type": by_type}

    before_stats = await _count_failures(before_start, activation_date)
    after_stats = await _count_failures(activation_date, after_end)

    before_total = before_stats["failure_rate"]
    after_total = after_stats["failure_rate"]

    if before_total > 0:
        improvement_pct = round(
            ((before_total - after_total) / before_total) * 100, 2
        )
    elif after_total == 0:
        improvement_pct = 0.0
    else:
        improvement_pct = -100.0  # failures appeared where there were none before

    # Decision logic.
    if after_total > before_total * 1.10:
        decision = "rollback"
    elif after_total <= before_total * 0.90:
        decision = "promote"
    else:
        decision = "hold"

    logger.info(
        "Tier 1a evaluation for experiment %s: %s (before=%d, after=%d, improvement=%.1f%%)",
        experiment_id, decision, before_total, after_total, improvement_pct,
    )

    return {
        "decision": decision,
        "before": before_stats,
        "after": after_stats,
        "improvement_pct": improvement_pct,
        "lookback_days": lookback_days,
        "activation_date": activation_date.isoformat(),
    }


async def get_role_prompt_status(session: AsyncSession) -> list[dict]:
    """Get the current prompt optimization status for all 7 pipeline roles.

    For each role reports whether there is an active prompt override, the
    number of experiments by status, and the latest failure count.
    """
    now = datetime.now(UTC)
    recent_cutoff = now - timedelta(days=90)
    statuses: list[dict] = []

    for role_name, detection_stage in ROLE_STAGE_MAP.items():
        # Active prompt override?
        active_prompt = await get_active_prompt(session, "role_prompt", role_name)

        # Count experiments for this role by status.
        exp_result = await session.execute(
            select(RSIExperiment.status, func.count().label("cnt"))
            .where(
                RSIExperiment.tier == "1a",
                RSIExperiment.name.contains(f"role_prompt_patch_{role_name}"),
            )
            .group_by(RSIExperiment.status)
        )
        experiments_by_status = {row.status: row.cnt for row in exp_result.all()}

        # Recent failure count for the stage.
        fail_count_result = await session.execute(
            select(func.count()).where(
                FailureRecord.detection_stage == detection_stage,
                FailureRecord.created_at >= recent_cutoff,
            )
        )
        recent_failure_count = fail_count_result.scalar() or 0

        # Total prompt versions registered for this role.
        pv_count_result = await session.execute(
            select(func.count()).where(
                PromptVersion.target_type == "role_prompt",
                PromptVersion.target_key == role_name,
            )
        )
        prompt_version_count = pv_count_result.scalar() or 0

        statuses.append({
            "role": role_name,
            "detection_stage": detection_stage,
            "has_active_override": active_prompt is not None,
            "prompt_versions": prompt_version_count,
            "experiments_by_status": experiments_by_status,
            "recent_failures_90d": recent_failure_count,
        })

    return statuses
