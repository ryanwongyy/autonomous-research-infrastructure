"""Tier 3c: Clusters killed paper ideas to discover potential new paper families."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.family_proposal import FamilyProposal
from app.services.rsi.experiment_manager import create_experiment
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)

# Common English stop words to filter out during keyword extraction
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "that", "this", "was", "are",
    "be", "has", "had", "have", "not", "no", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall", "been",
    "being", "its", "as", "if", "than", "too", "very", "just", "about",
    "also", "into", "over", "such", "so", "up", "out", "some", "all",
    "more", "most", "other", "each", "only", "own", "same", "then",
    "when", "where", "which", "who", "how", "what", "there", "their",
    "them", "they", "we", "our", "us", "my", "me", "he", "she", "his",
    "her", "you", "your", "any", "both", "few", "many", "much", "every",
    "between", "during", "before", "after", "above", "below", "because",
    "through", "while", "these", "those", "here", "data", "paper", "using",
    "based", "analysis", "study", "results", "approach", "method", "model",
    "use", "used", "new", "one", "two", "three", "however", "first", "well",
    "since", "found", "show", "shows", "shown", "given", "per", "et", "al",
    "see", "thus", "hence", "yet", "still", "even", "within", "across",
    "among", "via", "whether", "i", "e", "g", "vs", "etc", "ie", "eg",
    "null", "none", "true", "false",
})


def _extract_keywords(text: str | None) -> list[str]:
    """Extract meaningful keywords from text using simple bag-of-words approach."""
    if not text:
        return []
    # Lowercase, strip YAML keys, keep only alphabetical tokens
    text = text.lower()
    tokens = re.findall(r"[a-z]{3,}", text)
    return [t for t in tokens if t not in _STOP_WORDS]


def _cluster_papers_by_keywords(
    papers: list[dict],
    min_cluster_size: int,
) -> list[dict]:
    """Group papers by shared keywords to form thematic clusters.

    Uses a simple approach:
    1. Build a keyword frequency map across all papers.
    2. For each paper, pick its top keyword (most globally frequent).
    3. Group papers by their top keyword.
    4. Merge small clusters that share secondary keywords.
    """
    if not papers:
        return []

    # Build global keyword frequency
    global_freq: Counter[str] = Counter()
    paper_keywords: dict[str, list[str]] = {}

    for p in papers:
        combined_text = f"{p.get('kill_reason', '')} {p.get('idea_card_yaml', '')} {p.get('method', '')}"
        kws = _extract_keywords(combined_text)
        paper_keywords[p["id"]] = kws
        global_freq.update(set(kws))  # count each keyword once per paper

    # Assign each paper to a primary cluster keyword
    # Use the most globally-common keyword that the paper has (i.e. most shared theme)
    primary_clusters: dict[str, list[dict]] = defaultdict(list)
    for p in papers:
        kws = paper_keywords.get(p["id"], [])
        if not kws:
            continue
        # Score each keyword by global frequency, pick the best
        scored = sorted(set(kws), key=lambda k: global_freq[k], reverse=True)
        primary_key = scored[0]
        primary_clusters[primary_key].append(p)

    # Merge small clusters into nearby clusters based on secondary keywords
    merged_clusters: list[dict] = []
    leftover: list[dict] = []

    for keyword, cluster_papers in primary_clusters.items():
        if len(cluster_papers) >= min_cluster_size:
            merged_clusters.append({
                "primary_keyword": keyword,
                "papers": cluster_papers,
            })
        else:
            leftover.extend(cluster_papers)

    # Try to assign leftovers to existing clusters
    for p in leftover:
        kws = set(paper_keywords.get(p["id"], []))
        best_cluster = None
        best_overlap = 0
        for cluster in merged_clusters:
            # Check if this paper shares keywords with cluster members
            cluster_kws = set()
            for cp in cluster["papers"]:
                cluster_kws.update(paper_keywords.get(cp["id"], []))
            overlap = len(kws & cluster_kws)
            if overlap > best_overlap:
                best_overlap = overlap
                best_cluster = cluster
        if best_cluster is not None and best_overlap >= 2:
            best_cluster["papers"].append(p)

    # Format output
    results: list[dict] = []
    for idx, cluster in enumerate(merged_clusters):
        if len(cluster["papers"]) < min_cluster_size:
            continue

        # Extract common kill reasons and methods
        kill_reasons: Counter[str] = Counter()
        methods: Counter[str] = Counter()
        for p in cluster["papers"]:
            if p.get("kill_reason"):
                kill_reasons[p["kill_reason"]] += 1
            if p.get("method"):
                methods[p["method"]] += 1

        results.append({
            "cluster_id": idx,
            "theme": cluster["primary_keyword"],
            "paper_ids": [p["id"] for p in cluster["papers"]],
            "common_kill_reasons": [
                reason for reason, _ in kill_reasons.most_common(5)
            ],
            "common_methods": [
                method for method, _ in methods.most_common(5)
            ],
            "size": len(cluster["papers"]),
        })

    # Sort by cluster size descending
    results.sort(key=lambda c: c["size"], reverse=True)
    return results


async def cluster_killed_ideas(
    session: AsyncSession,
    min_cluster_size: int = 3,
) -> list[dict]:
    """Cluster papers killed at screening that don't fit existing families.

    Groups killed papers by kill_reason similarity and idea_card_yaml content.
    Uses simple keyword extraction (no LLM needed).

    Returns: [
        {
            "cluster_id": int,
            "theme": str,  # extracted common theme
            "paper_ids": [str],
            "common_kill_reasons": [str],
            "common_methods": [str],
            "size": int,
        }
    ]
    """
    # Query papers where funnel_stage="killed"
    killed_q = (
        select(
            Paper.id,
            Paper.kill_reason,
            Paper.idea_card_yaml,
            Paper.method,
            Paper.family_id,
        )
        .where(Paper.funnel_stage == "killed")
    )
    result = await session.execute(killed_q)
    rows = result.all()

    if not rows:
        return []

    # Convert to dicts for clustering
    papers = [
        {
            "id": row.id,
            "kill_reason": row.kill_reason,
            "idea_card_yaml": row.idea_card_yaml,
            "method": row.method,
            "family_id": row.family_id,
        }
        for row in rows
    ]

    # Cluster by keywords
    clusters = _cluster_papers_by_keywords(papers, min_cluster_size)

    return clusters


async def propose_new_family(
    session: AsyncSession,
    cluster: dict,
) -> dict:
    """Propose a new paper family from a cluster of killed ideas.

    Creates FamilyProposal with status="proposed".
    Creates RSIExperiment.

    Returns: {"experiment_id": int, "proposal_id": int, "proposed_family": dict}
    """
    theme = cluster.get("theme", "unknown")
    paper_ids = cluster.get("paper_ids", [])
    common_kill_reasons = cluster.get("common_kill_reasons", [])
    common_methods = cluster.get("common_methods", [])
    size = cluster.get("size", len(paper_ids))

    # Generate a proposed name and short name from the theme
    proposed_name = f"{theme.replace('_', ' ').title()} Research Family"
    proposed_short_name = theme[:12].upper().replace(" ", "_")

    # Estimate viability: larger clusters with fewer kill reasons are more viable
    kill_diversity = len(set(common_kill_reasons)) if common_kill_reasons else 1
    viability = min(1.0, (size / 10.0) * (1.0 / max(kill_diversity, 1)))
    viability = round(viability, 2)

    proposed_description = (
        f"Proposed family based on {size} killed papers with theme '{theme}'. "
        f"Common methods: {', '.join(common_methods) if common_methods else 'various'}. "
        f"Common kill reasons: {', '.join(common_kill_reasons[:3]) if common_kill_reasons else 'various'}."
    )

    # Create experiment
    experiment = await create_experiment(
        session,
        tier="3c",
        name=f"new_family_{proposed_short_name}",
        config_snapshot={
            "theme": theme,
            "paper_ids": paper_ids,
            "common_methods": common_methods,
            "common_kill_reasons": common_kill_reasons,
            "size": size,
        },
    )

    # Create proposal
    proposal = FamilyProposal(
        proposed_name=proposed_name,
        proposed_short_name=proposed_short_name,
        proposed_description=proposed_description,
        source_cluster_json=json.dumps({
            "cluster_id": cluster.get("cluster_id"),
            "theme": theme,
            "paper_ids": paper_ids,
        }),
        kill_reasons_json=json.dumps(common_kill_reasons),
        estimated_viability_score=viability,
        experiment_id=experiment.id,
        status="proposed",
    )
    session.add(proposal)
    await session.flush()

    logger.info(
        "Proposed new family '%s' (proposal=%s, experiment=%s, papers=%d)",
        proposed_name, proposal.id, experiment.id, size,
    )

    return {
        "experiment_id": experiment.id,
        "proposal_id": proposal.id,
        "proposed_family": {
            "name": proposed_name,
            "short_name": proposed_short_name,
            "description": proposed_description,
            "theme": theme,
            "paper_count": size,
            "viability_score": viability,
            "common_methods": common_methods,
            "common_kill_reasons": common_kill_reasons,
        },
    }


async def approve_family_proposal(
    session: AsyncSession,
    proposal_id: int,
) -> dict:
    """Approve a proposal and create the actual PaperFamily.

    Returns: {"family_id": str, "family": dict}
    """
    result = await session.execute(
        select(FamilyProposal).where(FamilyProposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise ValueError(f"FamilyProposal {proposal_id} not found")

    if proposal.status != "proposed":
        raise ValueError(
            f"Proposal {proposal_id} is not in 'proposed' status "
            f"(current: '{proposal.status}')"
        )

    # Generate a unique family ID (F<next_number>)
    max_id_q = select(func.count()).select_from(PaperFamily)
    total_families = (await session.execute(max_id_q)).scalar() or 0
    new_family_id = f"F{total_families + 1}"

    # Check for collision and increment if needed
    existing = await session.execute(
        select(PaperFamily.id).where(PaperFamily.id == new_family_id)
    )
    while existing.scalar_one_or_none() is not None:
        total_families += 1
        new_family_id = f"F{total_families + 1}"
        existing = await session.execute(
            select(PaperFamily.id).where(PaperFamily.id == new_family_id)
        )

    # Load cluster data to determine accepted methods
    (
        safe_json_loads(proposal.source_cluster_json, {})
    )
    (
        safe_json_loads(proposal.kill_reasons_json, [])
    )

    # Create the PaperFamily
    family = PaperFamily(
        id=new_family_id,
        name=proposal.proposed_name,
        short_name=proposal.proposed_short_name,
        description=proposal.proposed_description or "",
        lock_protocol_type="standard",  # default protocol
        canonical_questions=None,
        accepted_methods=None,
        venue_ladder=None,
        active=True,
    )
    session.add(family)

    # Update proposal
    proposal.status = "approved"
    proposal.resulting_family_id = new_family_id

    await session.flush()

    logger.info(
        "Approved family proposal %s -> family '%s' (%s)",
        proposal_id, new_family_id, proposal.proposed_name,
    )

    return {
        "family_id": new_family_id,
        "family": {
            "id": new_family_id,
            "name": family.name,
            "short_name": family.short_name,
            "description": family.description,
            "lock_protocol_type": family.lock_protocol_type,
            "active": family.active,
        },
    }


async def get_family_proposals(
    session: AsyncSession,
) -> list[dict]:
    """List all family proposals with their status."""
    query = (
        select(FamilyProposal)
        .order_by(FamilyProposal.created_at.desc())
    )
    result = await session.execute(query)
    proposals = result.scalars().all()

    return [
        {
            "id": p.id,
            "proposed_name": p.proposed_name,
            "proposed_short_name": p.proposed_short_name,
            "proposed_description": p.proposed_description,
            "source_cluster": (
                safe_json_loads(p.source_cluster_json, None)
            ),
            "kill_reasons": (
                safe_json_loads(p.kill_reasons_json, None)
            ),
            "estimated_viability_score": p.estimated_viability_score,
            "experiment_id": p.experiment_id,
            "status": p.status,
            "resulting_family_id": p.resulting_family_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in proposals
    ]
