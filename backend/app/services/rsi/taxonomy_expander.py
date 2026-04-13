"""Tier 4a: Clusters 'other' failures to discover new failure types and expand the taxonomy."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failure_record import FailureRecord
from app.models.failure_type_proposal import FailureTypeProposal
from app.services.rsi.experiment_manager import create_experiment
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# Common stop words to exclude from keyword extraction
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out", "off",
    "up", "down", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "that", "this", "it",
    "its", "also", "about", "which", "their", "them", "they", "these",
    "those", "what", "who", "whom", "any", "paper", "error", "issue",
    "found", "check", "review", "section", "data", "none", "null",
})

_TOKEN_RE = re.compile(r"[a-z_][a-z0-9_]{2,}")


def _extract_keywords(text: str | None) -> set[str]:
    """Extract meaningful lowercase keywords from text, filtering stop words."""
    if not text:
        return set()
    tokens = _TOKEN_RE.findall(text.lower())
    return {t for t in tokens if t not in _STOP_WORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two keyword sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def _cluster_by_keywords(
    records: list[tuple[int, set[str]]],
    threshold: float = 0.3,
) -> list[list[int]]:
    """Single-linkage clustering of record IDs by keyword Jaccard similarity.

    Each element in *records* is (record_id, keyword_set).
    Returns a list of clusters, each cluster being a list of record IDs.
    """
    # Adjacency via Jaccard threshold
    n = len(records)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(records[i][1], records[j][1]) >= threshold:
                union(i, j)

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(records[i][0])

    return list(clusters.values())


def _name_from_keywords(keyword_sets: list[set[str]], top_n: int = 3) -> str:
    """Generate a proposed failure-type name from the most frequent keywords."""
    freq: dict[str, int] = defaultdict(int)
    for kw_set in keyword_sets:
        for kw in kw_set:
            freq[kw] += 1

    top = sorted(freq, key=lambda k: freq[k], reverse=True)[:top_n]
    if not top:
        return "unknown_cluster"
    return "_".join(top)


async def cluster_other_failures(
    session: AsyncSession,
    min_cluster_size: int = 3,
) -> list[dict]:
    """Cluster FailureRecords where failure_type='other'.

    Groups by text similarity of resolution + corrective_action fields.
    Uses simple keyword extraction and overlap scoring.

    Returns list of cluster dicts sorted by size descending.
    """
    result = await session.execute(
        select(FailureRecord).where(FailureRecord.failure_type == "other")
    )
    others = result.scalars().all()

    if not others:
        logger.info("No 'other' failure records to cluster")
        return []

    # Build (record_id, keyword_set) pairs
    record_keywords: list[tuple[int, set[str]]] = []
    kw_by_id: dict[int, set[str]] = {}
    for rec in others:
        combined_text = " ".join(
            filter(None, [rec.resolution, rec.corrective_action])
        )
        kws = _extract_keywords(combined_text)
        record_keywords.append((rec.id, kws))
        kw_by_id[rec.id] = kws

    raw_clusters = _cluster_by_keywords(record_keywords, threshold=0.3)

    # Build output, filter by min_cluster_size
    clusters: list[dict] = []
    for idx, record_ids in enumerate(raw_clusters):
        if len(record_ids) < min_cluster_size:
            continue

        keyword_sets = [kw_by_id[rid] for rid in record_ids]
        all_keywords: set[str] = set()
        for ks in keyword_sets:
            all_keywords |= ks

        # Cluster cohesion: average pairwise Jaccard within the cluster
        if len(record_ids) >= 2:
            pair_count = 0
            jaccard_sum = 0.0
            for i in range(len(record_ids)):
                for j in range(i + 1, len(record_ids)):
                    jaccard_sum += _jaccard(
                        kw_by_id[record_ids[i]], kw_by_id[record_ids[j]]
                    )
                    pair_count += 1
            cohesion = jaccard_sum / pair_count if pair_count > 0 else 0.0
        else:
            cohesion = 1.0

        common = sorted(all_keywords, key=lambda k: sum(
            1 for ks in keyword_sets if k in ks
        ), reverse=True)[:10]

        clusters.append({
            "cluster_id": idx,
            "proposed_name": _name_from_keywords(keyword_sets),
            "description": (
                f"Cluster of {len(record_ids)} 'other' failures sharing "
                f"keywords: {', '.join(common[:5])}"
            ),
            "record_ids": sorted(record_ids),
            "size": len(record_ids),
            "common_keywords": common,
            "confidence": round(cohesion, 4),
        })

    clusters.sort(key=lambda c: c["size"], reverse=True)

    logger.info(
        "Clustered %d 'other' failures into %d clusters (min_size=%d)",
        len(others), len(clusters), min_cluster_size,
    )
    return clusters


async def propose_new_failure_type(
    session: AsyncSession,
    cluster: dict,
) -> dict:
    """Create a FailureTypeProposal from a cluster.

    Returns dict with proposal_id, experiment_id, and proposed_type details.
    """
    proposed_name = cluster["proposed_name"][:32]  # respect column length

    experiment = await create_experiment(
        session,
        tier="4a",
        name=f"taxonomy_expansion_{proposed_name}",
        config_snapshot={
            "cluster": {
                "cluster_id": cluster["cluster_id"],
                "size": cluster["size"],
                "common_keywords": cluster["common_keywords"],
                "confidence": cluster["confidence"],
            },
        },
    )

    proposal = FailureTypeProposal(
        proposed_type_name=proposed_name,
        proposed_description=cluster.get("description", ""),
        source_records_json=json.dumps(cluster["record_ids"]),
        cluster_size=cluster["size"],
        confidence=cluster["confidence"],
        status="proposed",
        experiment_id=experiment.id,
    )
    session.add(proposal)
    await session.flush()

    logger.info(
        "Proposed new failure type '%s' from cluster of %d records "
        "(proposal=%d, experiment=%d)",
        proposed_name, cluster["size"], proposal.id, experiment.id,
    )

    return {
        "proposal_id": proposal.id,
        "experiment_id": experiment.id,
        "proposed_type": {
            "name": proposed_name,
            "description": cluster.get("description", ""),
            "cluster_size": cluster["size"],
            "confidence": cluster["confidence"],
            "source_record_ids": cluster["record_ids"],
        },
    }


async def approve_failure_type(
    session: AsyncSession,
    proposal_id: int,
) -> dict:
    """Approve a failure type proposal and reclassify existing records.

    Updates all FailureRecords referenced in the proposal's source_records
    from 'other' to the newly approved type name.

    Returns dict with the approved type name and count of reclassified records.
    """
    result = await session.execute(
        select(FailureTypeProposal).where(FailureTypeProposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise ValueError(f"FailureTypeProposal {proposal_id} not found")

    if proposal.status != "proposed":
        raise ValueError(
            f"Proposal {proposal_id} is in status '{proposal.status}', "
            "only 'proposed' proposals can be approved"
        )

    # Parse source record IDs
    source_ids: list[int] = safe_json_loads(proposal.source_records_json, [])
    if not source_ids and proposal.source_records_json:
        logger.warning(
            "Could not parse source_records_json for proposal %d",
            proposal_id,
        )

    # Reclassify matching FailureRecords
    reclassified = 0
    if source_ids:
        records_result = await session.execute(
            select(FailureRecord).where(
                FailureRecord.id.in_(source_ids),
                FailureRecord.failure_type == "other",
            )
        )
        records = records_result.scalars().all()
        for rec in records:
            rec.failure_type = proposal.proposed_type_name
            reclassified += 1

    # Update proposal status
    proposal.status = "approved"
    proposal.approved_at = datetime.now(timezone.utc)

    await session.flush()

    logger.info(
        "Approved failure type '%s' (proposal=%d), reclassified %d records",
        proposal.proposed_type_name, proposal_id, reclassified,
    )

    return {
        "approved_type": proposal.proposed_type_name,
        "records_reclassified": reclassified,
    }


async def get_taxonomy_status(session: AsyncSession) -> dict:
    """Get current taxonomy status: type distribution, pending proposals, other count.

    Returns dict with failure type distribution, pending proposal count/list,
    total 'other' failures, and overall statistics.
    """
    # Failure type distribution
    type_dist_result = await session.execute(
        select(
            FailureRecord.failure_type,
            func.count().label("cnt"),
        )
        .group_by(FailureRecord.failure_type)
        .order_by(func.count().desc())
    )
    type_distribution: dict[str, int] = {
        row.failure_type: row.cnt for row in type_dist_result.all()
    }

    total_failures = sum(type_distribution.values())
    other_count = type_distribution.get("other", 0)

    # Pending proposals
    pending_result = await session.execute(
        select(FailureTypeProposal).where(
            FailureTypeProposal.status == "proposed"
        ).order_by(FailureTypeProposal.created_at.desc())
    )
    pending_proposals = pending_result.scalars().all()

    pending_list = [
        {
            "id": p.id,
            "proposed_type_name": p.proposed_type_name,
            "cluster_size": p.cluster_size,
            "confidence": p.confidence,
            "experiment_id": p.experiment_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pending_proposals
    ]

    # Recently approved proposals
    approved_result = await session.execute(
        select(FailureTypeProposal).where(
            FailureTypeProposal.status == "approved"
        ).order_by(FailureTypeProposal.approved_at.desc()).limit(10)
    )
    approved_proposals = approved_result.scalars().all()

    approved_list = [
        {
            "id": p.id,
            "proposed_type_name": p.proposed_type_name,
            "cluster_size": p.cluster_size,
            "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        }
        for p in approved_proposals
    ]

    # Known canonical types from the classifier mapping
    canonical_types = sorted({
        "formatting", "data_error", "hallucination", "causal_overreach",
        "source_drift", "design_violation", "logic_error", "other",
    })

    # Types discovered via taxonomy expansion (in distribution but not canonical)
    discovered_types = sorted(
        t for t in type_distribution if t not in canonical_types
    )

    return {
        "total_failures": total_failures,
        "other_count": other_count,
        "other_percentage": round(
            other_count / total_failures * 100, 2
        ) if total_failures > 0 else 0.0,
        "type_distribution": type_distribution,
        "canonical_types": canonical_types,
        "discovered_types": discovered_types,
        "pending_proposals": pending_list,
        "pending_count": len(pending_list),
        "recently_approved": approved_list,
    }
