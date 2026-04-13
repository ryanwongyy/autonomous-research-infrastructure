"""Novelty detection: compares paper designs against existing corpus.

Two-layer approach:
1. Fast structural comparison (Jaccard on tokens + data source overlap)
2. Semantic comparison via LLM for borderline cases (similarity 0.2-0.7)
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.novelty_check import NoveltyCheck
from app.models.paper import Paper
from app.models.lock_artifact import LockArtifact
from app.services.storage.lock_manager import extract_design_fields

logger = logging.getLogger(__name__)

_SEMANTIC_CHECK_PROMPT = """\
You are a novelty detector for academic research designs. Compare these two designs and assess how similar they are.

Design A (new paper):
- Questions: {questions_a}
- Data sources: {sources_a}
- Method: {method_a}

Design B (existing paper):
- Questions: {questions_b}
- Data sources: {sources_b}
- Method: {method_b}

Rate the semantic similarity from 0.0 (completely different research) to 1.0 (same study, possibly rephrased). Consider whether the studies would answer the same question using the same evidence, even if worded differently.

Return ONLY a JSON object: {{"similarity": float, "rationale": "one sentence"}}"""


async def check_novelty(
    session: AsyncSession, paper_id: str
) -> NoveltyCheck:
    """Compare a paper's design against all same-family papers.

    Uses structural comparison first, then LLM-based semantic comparison
    for borderline cases.

    Verdict:
    - novel: similarity < 0.3 with all existing papers
    - marginal: similarity 0.3-0.6 with at least one paper
    - derivative: similarity > 0.6 with at least one paper
    """
    paper_result = await session.execute(
        select(Paper).where(Paper.id == paper_id)
    )
    paper = paper_result.scalar_one_or_none()
    if paper is None:
        raise ValueError(f"Paper '{paper_id}' not found")

    # Load this paper's design
    lock_result = await session.execute(
        select(LockArtifact).where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        ).limit(1)
    )
    lock = lock_result.scalar_one_or_none()

    if lock is None:
        # No lock artifact — cannot check novelty, pass by default
        check = NoveltyCheck(
            paper_id=paper_id,
            checked_against_count=0,
            highest_similarity_score=0.0,
            similar_paper_ids_json=json.dumps([]),
            verdict="novel",
            model_used="structural",
            check_details_json=json.dumps({"note": "No lock artifact found; novelty assumed."}),
        )
        session.add(check)
        await session.flush()
        return check

    design = extract_design_fields(lock.lock_yaml)

    # Load all other papers in the same family that have lock artifacts
    other_locks_result = await session.execute(
        select(LockArtifact, Paper)
        .join(Paper, LockArtifact.paper_id == Paper.id)
        .where(
            Paper.family_id == paper.family_id,
            Paper.id != paper_id,
            LockArtifact.is_active.is_(True),
        )
    )
    other_locks = other_locks_result.all()

    checked_count = len(other_locks)
    highest_score = 0.0
    similar_ids = []
    details = []

    for other_lock, other_paper in other_locks:
        other_design = extract_design_fields(other_lock.lock_yaml)
        structural_sim = _structural_similarity(design, other_design)

        # For borderline cases, run semantic comparison via LLM
        sim = structural_sim
        semantic_rationale = None
        if 0.2 <= structural_sim <= 0.7:
            semantic_sim, semantic_rationale = await _semantic_similarity(
                design, other_design
            )
            if semantic_sim is not None:
                sim = max(structural_sim, semantic_sim)

        if sim > highest_score:
            highest_score = sim
        if sim > 0.3:
            similar_ids.append({"paper_id": other_paper.id, "similarity": round(sim, 3)})
        detail_entry = {
            "compared_to": other_paper.id,
            "structural_similarity": round(structural_sim, 3),
            "similarity": round(sim, 3),
        }
        if semantic_rationale:
            detail_entry["semantic_rationale"] = semantic_rationale
        details.append(detail_entry)

    # Determine verdict
    if highest_score > 0.6:
        verdict = "derivative"
    elif highest_score > 0.3:
        verdict = "marginal"
    else:
        verdict = "novel"

    check = NoveltyCheck(
        paper_id=paper_id,
        checked_against_count=checked_count,
        highest_similarity_score=round(highest_score, 3),
        similar_paper_ids_json=json.dumps(similar_ids),
        verdict=verdict,
        model_used="structural+semantic",
        check_details_json=json.dumps(details),
    )
    session.add(check)
    await session.flush()

    logger.info(
        "Novelty check for %s: verdict=%s, highest_sim=%.3f, checked=%d papers",
        paper_id, verdict, highest_score, checked_count,
    )
    return check


async def _semantic_similarity(
    design_a: dict, design_b: dict
) -> tuple[float | None, str | None]:
    """Use LLM to assess semantic similarity between two research designs.

    Returns (similarity_score, rationale) or (None, None) if LLM unavailable.
    """
    try:
        from app.services.llm.router import get_generation_provider

        provider, model = await get_generation_provider()
        prompt = _SEMANTIC_CHECK_PROMPT.format(
            questions_a=", ".join(design_a.get("research_questions", [])),
            sources_a=", ".join(design_a.get("data_sources", [])),
            method_a=design_a.get("method", ""),
            questions_b=", ".join(design_b.get("research_questions", [])),
            sources_b=", ".join(design_b.get("data_sources", [])),
            method_b=design_b.get("method", ""),
        )
        response = await provider.complete(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0.0,
            max_tokens=256,
        )
        # Parse the JSON response
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
        score = float(data.get("similarity", 0.0))
        rationale = data.get("rationale", "")
        return min(max(score, 0.0), 1.0), rationale
    except Exception as e:
        logger.warning("Semantic novelty check failed: %s", e)
        return None, None


def _structural_similarity(design_a: dict, design_b: dict) -> float:
    """Compute structural similarity between two designs.

    Compares research_questions, data_sources, and method fields.
    Returns 0.0 (no overlap) to 1.0 (identical).
    """
    scores = []

    # Question overlap (Jaccard on tokenized words)
    q_a = _tokenize_list(design_a.get("research_questions", []))
    q_b = _tokenize_list(design_b.get("research_questions", []))
    scores.append(_jaccard(q_a, q_b))

    # Data source overlap
    d_a = set(s.lower() for s in design_a.get("data_sources", []))
    d_b = set(s.lower() for s in design_b.get("data_sources", []))
    scores.append(_jaccard(d_a, d_b))

    # Method overlap
    m_a = str(design_a.get("method", "") or "").lower()
    m_b = str(design_b.get("method", "") or "").lower()
    if m_a and m_b:
        scores.append(1.0 if m_a == m_b else 0.0)

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _tokenize_list(items: list) -> set[str]:
    """Tokenize a list of strings into a set of lowered words."""
    tokens: set[str] = set()
    for item in items:
        for word in str(item).lower().split():
            if len(word) > 2:
                tokens.add(word)
    return tokens


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0
