"""Creates and verifies lock artifacts for paper design freezes."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.services.provenance.hasher import hash_content
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lock protocol field definitions by family type
# ---------------------------------------------------------------------------

LOCK_IMMUTABLE_FIELDS: dict[str, list[str]] = {
    "empirical_causal": [
        "treatment_definition",
        "outcome_definitions",
        "sample_rules",
        "estimand",
        "identification_strategy",
        "source_lineage",
    ],
    "measurement_text": [
        "corpus_inclusion_rules",
        "ontology",
        "coding_schema",
        "unit_of_analysis",
        "aggregation_rules",
    ],
    "comparative_historical": [
        "case_set",
        "rival_explanations",
        "period_boundaries",
        "comparison_logic",
        "source_hierarchy",
    ],
    "doctrinal": [
        "legal_question",
        "jurisdictional_scope",
        "interpretive_framework",
        "source_hierarchy",
        "contrary_authority_protocol",
    ],
    "process_tracing": [
        "case_set",
        "mechanism",
        "evidentiary_threshold",
        "hoop_tests",
        "smoking_gun_tests",
    ],
    "theory": [
        "assumptions",
        "solution_concept",
        "policy_target",
        "players",
        "timing",
        "equilibrium_concept",
    ],
    "synthesis_bibliometric": [
        "search_universe",
        "inclusion_logic",
        "synthesis_method",
        "screening_protocol",
        "deduplication_rules",
    ],
}

LOCK_MUTABLE_FIELDS: dict[str, list[str]] = {
    "empirical_causal": [
        "implementation_details",
        "wording",
        "appendix_expansion",
    ],
    "measurement_text": ["classifier_tuning"],
    "comparative_historical": ["archival_fill_in"],
    "doctrinal": ["prose", "additional_authorities"],
    "process_tracing": ["extra_corroboration"],
    "theory": ["exposition", "illustrative_examples"],
    "synthesis_bibliometric": [
        "typo_fixes",
        "expanded_reporting",
    ],
}


async def create_lock(
    session: AsyncSession,
    paper_id: str,
    lock_yaml_content: str,
    locked_by: str = "system",
    source_manifest_hash: str | None = None,
    narrative_memo: str | None = None,
) -> LockArtifact:
    """Create a new lock artifact for a paper.

    Steps:
    1. Load the paper and its family.
    2. Determine immutable/mutable fields from the family's lock protocol.
    3. Compute SHA-256 hash of the lock YAML.
    4. Create LockArtifact record.
    5. Update Paper.lock_hash, lock_version, lock_timestamp.
    6. If the paper already has an active lock, supersede it (new major version).

    Raises ValueError if the paper or family is not found, or the protocol type
    is unrecognised.
    """
    # 1. Load paper and family.
    paper = await _get_paper(session, paper_id)
    if paper is None:
        raise ValueError(f"Paper '{paper_id}' not found.")

    if paper.family_id is None:
        raise ValueError(f"Paper '{paper_id}' has no family_id assigned.")

    family = await _get_family(session, paper.family_id)
    if family is None:
        raise ValueError(f"Paper family '{paper.family_id}' not found.")

    protocol_type = family.lock_protocol_type

    # 2. Determine field lists.
    immutable = LOCK_IMMUTABLE_FIELDS.get(protocol_type)
    if immutable is None:
        raise ValueError(
            f"Unknown lock protocol type '{protocol_type}'. "
            f"Known types: {list(LOCK_IMMUTABLE_FIELDS.keys())}"
        )
    mutable = LOCK_MUTABLE_FIELDS.get(protocol_type, [])

    # 3. Compute hash.
    lock_hash = hash_content(lock_yaml_content.encode("utf-8"))

    # 4 & 6. Handle existing active lock (supersede it).
    new_version = 1
    stmt = (
        select(LockArtifact)
        .where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        )
        .order_by(LockArtifact.version.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    existing_lock: LockArtifact | None = result.scalar_one_or_none()

    if existing_lock is not None:
        new_version = existing_lock.version + 1
        existing_lock.is_active = False
        # superseded_by will be set after the new lock is flushed and has an id.
        session.add(existing_lock)

    # 4. Create the new LockArtifact.
    lock_artifact = LockArtifact(
        paper_id=paper_id,
        family_id=family.id,
        lock_protocol_type=protocol_type,
        version=new_version,
        lock_hash=lock_hash,
        lock_yaml=lock_yaml_content,
        narrative_memo=narrative_memo,
        source_manifest_hash=source_manifest_hash,
        immutable_fields=json.dumps(immutable),
        mutable_fields=json.dumps(mutable),
        locked_by=locked_by,
        is_active=True,
    )
    session.add(lock_artifact)

    # Flush to obtain the new lock artifact's id.
    await session.flush()

    # Set superseded_by on the old lock now that we have the new id.
    if existing_lock is not None:
        existing_lock.superseded_by = lock_artifact.id
        session.add(existing_lock)

    # 5. Update paper-level lock fields.
    paper.lock_hash = lock_hash
    paper.lock_version = new_version
    paper.lock_timestamp = datetime.now(UTC)
    session.add(paper)

    await session.flush()

    logger.info(
        "Created lock v%d for paper %s (protocol=%s, hash=%s)",
        new_version,
        paper_id,
        protocol_type,
        lock_hash[:16],
    )
    return lock_artifact


async def verify_lock(session: AsyncSession, paper_id: str) -> dict:
    """Verify the current lock artifact is intact.

    Returns a dict with:
    - valid: overall validity
    - hash_match: whether stored hash matches recomputed hash
    - violations: any detected issues
    """
    paper = await _get_paper(session, paper_id)
    if paper is None:
        return {
            "valid": False,
            "paper_id": paper_id,
            "lock_version": 0,
            "stored_hash": None,
            "computed_hash": None,
            "hash_match": False,
            "protocol_type": None,
            "immutable_fields": [],
            "violations": ["Paper not found."],
        }

    # Fetch active lock.
    stmt = (
        select(LockArtifact)
        .where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    lock: LockArtifact | None = result.scalar_one_or_none()

    if lock is None:
        return {
            "valid": False,
            "paper_id": paper_id,
            "lock_version": 0,
            "stored_hash": paper.lock_hash,
            "computed_hash": None,
            "hash_match": False,
            "protocol_type": None,
            "immutable_fields": [],
            "violations": ["No active lock artifact found for this paper."],
        }

    # Recompute hash of the stored YAML.
    computed_hash = hash_content(lock.lock_yaml.encode("utf-8"))
    hash_match = computed_hash == lock.lock_hash

    violations: list[str] = []

    if not hash_match:
        violations.append(
            f"Hash mismatch: stored={lock.lock_hash[:16]}..., "
            f"computed={computed_hash[:16]}..."
        )

    # Check paper-level hash consistency.
    if paper.lock_hash and paper.lock_hash != lock.lock_hash:
        violations.append(
            "Paper.lock_hash does not match the active LockArtifact.lock_hash."
        )

    # Parse immutable fields for reporting.
    immutable_fields: list[str] = safe_json_loads(lock.immutable_fields, [])
    if not immutable_fields and lock.immutable_fields:
        violations.append("Could not parse immutable_fields JSON from lock artifact.")

    return {
        "valid": hash_match and len(violations) == 0,
        "paper_id": paper_id,
        "lock_version": lock.version,
        "stored_hash": lock.lock_hash,
        "computed_hash": computed_hash,
        "hash_match": hash_match,
        "protocol_type": lock.lock_protocol_type,
        "immutable_fields": immutable_fields,
        "violations": violations,
    }


async def check_field_mutation(
    old_lock_yaml: str, new_lock_yaml: str, protocol_type: str
) -> dict:
    """Check if any immutable fields were changed between lock versions.

    Parses both YAML documents and compares the values of all immutable fields
    for the given protocol type.

    Returns:
        {
            "mutated": bool,
            "mutated_fields": list[str],   -- immutable fields that changed
            "mutable_changes": list[str],   -- mutable fields that changed (allowed)
        }
    """
    immutable = LOCK_IMMUTABLE_FIELDS.get(protocol_type, [])
    mutable = LOCK_MUTABLE_FIELDS.get(protocol_type, [])

    try:
        old_data: dict = yaml.safe_load(old_lock_yaml) or {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse old lock YAML: %s", exc)
        return {
            "mutated": True,
            "mutated_fields": ["<parse_error_old>"],
            "mutable_changes": [],
        }

    try:
        new_data: dict = yaml.safe_load(new_lock_yaml) or {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse new lock YAML: %s", exc)
        return {
            "mutated": True,
            "mutated_fields": ["<parse_error_new>"],
            "mutable_changes": [],
        }

    mutated_fields: list[str] = []
    mutable_changes: list[str] = []

    # Check immutable fields.
    for field in immutable:
        old_val = old_data.get(field)
        new_val = new_data.get(field)
        if old_val != new_val:
            mutated_fields.append(field)
            logger.warning(
                "Immutable field '%s' changed in protocol '%s'",
                field,
                protocol_type,
            )

    # Check mutable fields (informational).
    for field in mutable:
        old_val = old_data.get(field)
        new_val = new_data.get(field)
        if old_val != new_val:
            mutable_changes.append(field)

    return {
        "mutated": len(mutated_fields) > 0,
        "mutated_fields": mutated_fields,
        "mutable_changes": mutable_changes,
    }


def extract_design_fields(lock_yaml_content: str) -> dict:
    """Parse the lock YAML and return key design fields for drift checking.

    Returns a dict with keys:
    - research_questions: list[str]
    - data_sources: list[str]
    - expected_outputs: list[str]
    - identification_strategy: str | None
    - method: str | None

    Missing fields return empty lists or None.
    """
    try:
        data: dict = yaml.safe_load(lock_yaml_content) or {}
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse lock YAML for design extraction: %s", exc)
        return {
            "research_questions": [],
            "data_sources": [],
            "expected_outputs": [],
            "identification_strategy": None,
            "method": None,
        }

    def _as_list(val) -> list[str]:
        if isinstance(val, list):
            return [str(v) for v in val]
        if isinstance(val, str):
            return [val]
        return []

    return {
        "research_questions": _as_list(data.get("research_questions", data.get("research_question", []))),
        "data_sources": _as_list(data.get("data_sources", data.get("source_lineage", []))),
        "expected_outputs": _as_list(data.get("expected_outputs", data.get("output_tables", []))),
        "identification_strategy": data.get("identification_strategy") or data.get("estimand"),
        "method": data.get("method") or data.get("synthesis_method"),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_paper(session: AsyncSession, paper_id: str) -> Paper | None:
    """Fetch a paper by ID."""
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_family(session: AsyncSession, family_id: str) -> PaperFamily | None:
    """Fetch a paper family by ID."""
    stmt = select(PaperFamily).where(PaperFamily.id == family_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
