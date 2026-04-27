"""Tier 3b: Analyzes role boundary failures and proposes role splits/merges."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failure_record import FailureRecord
from app.models.paper import Paper
from app.models.role_config import RoleConfig
from app.services.rsi.experiment_manager import create_experiment
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

PIPELINE_ROLES = [
    "scout",
    "designer",
    "data_steward",
    "analyst",
    "drafter",
    "verifier",
    "packager",
]

# Map roles to the funnel stages they operate at
ROLE_TO_STAGES: dict[str, list[str]] = {
    "scout": ["idea", "screened"],
    "designer": ["screened", "locked"],
    "data_steward": ["locked", "ingesting"],
    "analyst": ["ingesting", "analyzing"],
    "drafter": ["analyzing", "drafting"],
    "verifier": ["drafting", "reviewing"],
    "packager": ["reviewing", "candidate"],
}

# Derive the boundary stages: the overlapping stage between consecutive roles
# e.g. scout->designer boundary is "screened" (scout's exit, designer's entry)
_BOUNDARY_STAGES: list[tuple[str, str, list[str]]] = []
for i in range(len(PIPELINE_ROLES) - 1):
    _from = PIPELINE_ROLES[i]
    _to = PIPELINE_ROLES[i + 1]
    # The boundary is the overlap between the from-role's stages and to-role's stages
    overlap = set(ROLE_TO_STAGES[_from]) & set(ROLE_TO_STAGES[_to])
    _BOUNDARY_STAGES.append((_from, _to, sorted(overlap)))


async def analyze_role_boundary_failures(
    session: AsyncSession,
    lookback_days: int = 180,
) -> dict:
    """Analyze failures at role boundaries (handoff points between consecutive roles).

    For each pair of consecutive roles, count failures whose detection_stage
    falls in the boundary region.

    Returns: {
        "boundaries": [
            {
                "from_role": str, "to_role": str,
                "failure_count": int,
                "top_failure_types": [{"type": str, "count": int}],
                "friction_score": float  # failures / total papers through this boundary
            }
        ],
        "highest_friction": {"from": str, "to": str, "score": float},
    }
    """
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    boundaries: list[dict] = []
    highest_friction: dict = {"from": "", "to": "", "score": 0.0}

    for from_role, to_role, boundary_stages in _BOUNDARY_STAGES:
        if not boundary_stages:
            boundaries.append(
                {
                    "from_role": from_role,
                    "to_role": to_role,
                    "failure_count": 0,
                    "top_failure_types": [],
                    "friction_score": 0.0,
                }
            )
            continue

        # Count failures at the boundary stages
        failure_q = (
            select(
                FailureRecord.failure_type,
                func.count().label("cnt"),
            )
            .where(
                FailureRecord.detection_stage.in_(boundary_stages),
                FailureRecord.created_at >= cutoff,
            )
            .group_by(FailureRecord.failure_type)
            .order_by(func.count().desc())
        )
        failure_rows = (await session.execute(failure_q)).all()

        failure_count = sum(row.cnt for row in failure_rows)
        top_failure_types = [
            {"type": row.failure_type, "count": row.cnt} for row in failure_rows[:5]
        ]

        # Total papers that passed through the boundary stages (to compute friction)
        # A paper "passes through" if its funnel_stage is at or beyond the boundary
        all_stages_at_or_beyond = set()
        found_boundary = False
        for stage_list in ROLE_TO_STAGES.values():
            for s in stage_list:
                if s in boundary_stages:
                    found_boundary = True
                if found_boundary:
                    all_stages_at_or_beyond.add(s)

        paper_count_q = (
            select(func.count())
            .select_from(Paper)
            .where(
                Paper.funnel_stage.in_(all_stages_at_or_beyond),
                Paper.created_at >= cutoff,
            )
        )
        total_papers = (await session.execute(paper_count_q)).scalar() or 0

        friction_score = failure_count / total_papers if total_papers else 0.0

        boundary_entry = {
            "from_role": from_role,
            "to_role": to_role,
            "failure_count": failure_count,
            "top_failure_types": top_failure_types,
            "friction_score": round(friction_score, 4),
        }
        boundaries.append(boundary_entry)

        if friction_score > highest_friction["score"]:
            highest_friction = {
                "from": from_role,
                "to": to_role,
                "score": round(friction_score, 4),
            }

    return {
        "boundaries": boundaries,
        "highest_friction": highest_friction,
    }


async def propose_role_split(
    session: AsyncSession,
    role_name: str,
    split_rationale: str | None = None,
) -> dict:
    """Propose splitting a role into sub-roles based on failure analysis.

    Creates two RoleConfig entries (sub_a and sub_b) with parent_role=role_name.
    Creates RSIExperiment.

    Returns: {"experiment_id": int, "new_roles": [dict, dict], "rationale": str}
    """
    if role_name not in PIPELINE_ROLES:
        raise ValueError(f"Invalid role '{role_name}'. Must be one of: {', '.join(PIPELINE_ROLES)}")

    stages = ROLE_TO_STAGES[role_name]
    if len(stages) < 2:
        raise ValueError(
            f"Role '{role_name}' only covers {len(stages)} stage(s) and cannot be split further."
        )

    # Determine how to split the stages between sub-roles
    mid = len(stages) // 2
    stages_a = stages[:mid] if mid > 0 else stages[:1]
    stages_b = stages[mid:]

    rationale = split_rationale or (
        f"Splitting '{role_name}' into '{role_name}_sub_a' (stages {stages_a}) "
        f"and '{role_name}_sub_b' (stages {stages_b}) to reduce boundary friction."
    )

    # Create experiment
    experiment = await create_experiment(
        session,
        tier="3b",
        name=f"split_{role_name}",
        config_snapshot={
            "original_role": role_name,
            "sub_a_stages": stages_a,
            "sub_b_stages": stages_b,
            "rationale": rationale,
        },
    )

    # Create the two sub-role configs
    role_a = RoleConfig(
        role_name=f"{role_name}_sub_a",
        parent_role=role_name,
        status="proposed",
        capabilities_json=json.dumps(
            {
                "inherited_from": role_name,
                "stages": stages_a,
            }
        ),
        boundaries_json=json.dumps(
            {
                "entry_stage": stages_a[0],
                "exit_stage": stages_a[-1],
            }
        ),
        prerequisite_stages_json=json.dumps(stages_a),
        experiment_id=experiment.id,
    )
    role_b = RoleConfig(
        role_name=f"{role_name}_sub_b",
        parent_role=role_name,
        status="proposed",
        capabilities_json=json.dumps(
            {
                "inherited_from": role_name,
                "stages": stages_b,
            }
        ),
        boundaries_json=json.dumps(
            {
                "entry_stage": stages_b[0],
                "exit_stage": stages_b[-1],
            }
        ),
        prerequisite_stages_json=json.dumps(stages_b),
        experiment_id=experiment.id,
    )
    session.add(role_a)
    session.add(role_b)
    await session.flush()

    logger.info(
        "Proposed role split for '%s' -> ('%s', '%s'), experiment=%s",
        role_name,
        role_a.role_name,
        role_b.role_name,
        experiment.id,
    )

    def _role_to_dict(rc: RoleConfig) -> dict:
        return {
            "id": rc.id,
            "role_name": rc.role_name,
            "parent_role": rc.parent_role,
            "status": rc.status,
            "capabilities": safe_json_loads(rc.capabilities_json, None),
            "boundaries": safe_json_loads(rc.boundaries_json, None),
            "prerequisite_stages": (safe_json_loads(rc.prerequisite_stages_json, None)),
            "experiment_id": rc.experiment_id,
        }

    return {
        "experiment_id": experiment.id,
        "new_roles": [_role_to_dict(role_a), _role_to_dict(role_b)],
        "rationale": rationale,
    }


async def propose_role_merge(
    session: AsyncSession,
    role_a: str,
    role_b: str,
) -> dict:
    """Propose merging two consecutive roles.

    Creates one RoleConfig with capabilities from both.
    Returns: {"experiment_id": int, "merged_role": dict, "rationale": str}
    """
    if role_a not in PIPELINE_ROLES:
        raise ValueError(f"Invalid role '{role_a}'. Must be one of: {', '.join(PIPELINE_ROLES)}")
    if role_b not in PIPELINE_ROLES:
        raise ValueError(f"Invalid role '{role_b}'. Must be one of: {', '.join(PIPELINE_ROLES)}")

    # Ensure roles are consecutive
    idx_a = PIPELINE_ROLES.index(role_a)
    idx_b = PIPELINE_ROLES.index(role_b)
    if abs(idx_a - idx_b) != 1:
        raise ValueError(
            f"Roles '{role_a}' and '{role_b}' are not consecutive in the pipeline. "
            f"Only consecutive roles can be merged."
        )

    # Ensure order: earlier role first
    if idx_a > idx_b:
        role_a, role_b = role_b, role_a

    merged_stages = sorted(
        set(ROLE_TO_STAGES[role_a]) | set(ROLE_TO_STAGES[role_b]),
        key=lambda s: _all_stages_ordered().index(s) if s in _all_stages_ordered() else 999,
    )
    merged_name = f"{role_a}_{role_b}_merged"

    rationale = (
        f"Merging '{role_a}' and '{role_b}' into '{merged_name}' to reduce "
        f"handoff friction. Combined stages: {merged_stages}."
    )

    # Create experiment
    experiment = await create_experiment(
        session,
        tier="3b",
        name=f"merge_{role_a}_{role_b}",
        config_snapshot={
            "role_a": role_a,
            "role_b": role_b,
            "merged_stages": merged_stages,
            "rationale": rationale,
        },
    )

    merged_role = RoleConfig(
        role_name=merged_name,
        parent_role=None,
        status="proposed",
        capabilities_json=json.dumps(
            {
                "merged_from": [role_a, role_b],
                "stages": merged_stages,
                "capabilities_a": {"role": role_a, "stages": ROLE_TO_STAGES[role_a]},
                "capabilities_b": {"role": role_b, "stages": ROLE_TO_STAGES[role_b]},
            }
        ),
        boundaries_json=json.dumps(
            {
                "entry_stage": merged_stages[0],
                "exit_stage": merged_stages[-1],
            }
        ),
        prerequisite_stages_json=json.dumps(merged_stages),
        experiment_id=experiment.id,
    )
    session.add(merged_role)
    await session.flush()

    logger.info(
        "Proposed role merge '%s' + '%s' -> '%s', experiment=%s",
        role_a,
        role_b,
        merged_name,
        experiment.id,
    )

    return {
        "experiment_id": experiment.id,
        "merged_role": {
            "id": merged_role.id,
            "role_name": merged_role.role_name,
            "status": merged_role.status,
            "capabilities": safe_json_loads(merged_role.capabilities_json, None),
            "boundaries": safe_json_loads(merged_role.boundaries_json, None),
            "prerequisite_stages": safe_json_loads(merged_role.prerequisite_stages_json, None),
            "experiment_id": merged_role.experiment_id,
        },
        "rationale": rationale,
    }


async def get_role_architecture(
    session: AsyncSession,
    family_id: str | None = None,
) -> list[dict]:
    """Get current role architecture: active roles, any proposed splits/merges."""
    query = select(RoleConfig)
    if family_id is not None:
        query = query.where(RoleConfig.family_id == family_id)

    query = query.order_by(RoleConfig.role_name)
    result = await session.execute(query)
    configs = result.scalars().all()

    # Build the full picture: default pipeline roles + any overrides/proposals
    config_by_role: dict[str, list[RoleConfig]] = defaultdict(list)
    for c in configs:
        config_by_role[c.role_name].append(c)

    output: list[dict] = []

    # First, show the default pipeline roles
    for role in PIPELINE_ROLES:
        role_configs = config_by_role.pop(role, [])
        active_config = next((c for c in role_configs if c.status == "active"), None)

        entry: dict = {
            "role_name": role,
            "stages": ROLE_TO_STAGES[role],
            "status": active_config.status if active_config else "default",
            "config_id": active_config.id if active_config else None,
            "family_id": active_config.family_id if active_config else family_id,
            "parent_role": None,
            "proposed_changes": [],
        }

        # Any proposed sub-roles or modifications
        proposed = [c for c in role_configs if c.status == "proposed"]
        for p in proposed:
            entry["proposed_changes"].append(
                {
                    "config_id": p.id,
                    "type": "split" if p.parent_role else "modification",
                    "new_role_name": p.role_name,
                    "experiment_id": p.experiment_id,
                    "capabilities": safe_json_loads(p.capabilities_json, None),
                }
            )

        output.append(entry)

    # Then, show any additional roles not in the default pipeline (e.g. sub-roles, merged roles)
    for role_name, role_configs in sorted(config_by_role.items()):
        for c in role_configs:
            output.append(
                {
                    "role_name": c.role_name,
                    "stages": safe_json_loads(c.prerequisite_stages_json, []),
                    "status": c.status,
                    "config_id": c.id,
                    "family_id": c.family_id,
                    "parent_role": c.parent_role,
                    "proposed_changes": [],
                    "capabilities": safe_json_loads(c.capabilities_json, None),
                    "experiment_id": c.experiment_id,
                }
            )

    return output


def _all_stages_ordered() -> list[str]:
    """Return all funnel stages in pipeline order (used for sorting)."""
    return [
        "idea",
        "screened",
        "locked",
        "ingesting",
        "analyzing",
        "drafting",
        "reviewing",
        "revision",
        "benchmark",
        "candidate",
        "submitted",
        "public",
        "killed",
    ]
