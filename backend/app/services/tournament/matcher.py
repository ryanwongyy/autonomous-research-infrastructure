import random
from dataclasses import dataclass


@dataclass
class PaperInfo:
    id: str
    source: str
    matches_played: int
    family_id: str | None = None


def generate_batches(
    papers: list[PaperInfo],
    num_batches: int = 10,
    matches_per_batch: int = 5,
    family_id: str | None = None,
) -> list[list[tuple[str, str]]]:
    """Generate match batches ensuring no paper repeats within a batch.

    When *family_id* is supplied, only papers belonging to that family are
    considered.  Cross-source mixing (AI vs benchmark) is preserved within
    the family.  No pair of papers may fight more than once across all
    batches in a single call (no repeat matches within the run).

    Prefers papers with fewer matches played.
    """
    # Filter to the target family if specified
    pool = papers
    if family_id:
        pool = [p for p in papers if p.family_id == family_id]

    if len(pool) < 2:
        return []

    batches: list[list[tuple[str, str]]] = []
    # Track all pairs already matched in this run to avoid repeats
    seen_pairs: set[tuple[str, str]] = set()

    for _ in range(num_batches):
        batch = _generate_single_batch(pool, matches_per_batch, seen_pairs)
        if batch:
            batches.append(batch)

    return batches


def _generate_single_batch(
    papers: list[PaperInfo],
    matches_per_batch: int,
    seen_pairs: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Generate a single batch of matches with no paper repeating.

    *seen_pairs* is mutated in place — each new pairing is added so that
    subsequent batches do not duplicate it.
    """
    # Weight papers by inverse of matches played (prefer less-tested papers)
    weighted = []
    for p in papers:
        weight = 1.0 / (1 + p.matches_played)
        weighted.append((p, weight))

    batch: list[tuple[str, str]] = []
    used_in_batch: set[str] = set()

    for _ in range(matches_per_batch):
        available = [(p, w) for p, w in weighted if p.id not in used_in_batch]
        if len(available) < 2:
            break

        # Weighted random selection for first paper
        pool = [p for p, _ in available]
        weights = [w for _, w in available]
        total = sum(weights)
        weights = [w / total for w in weights]

        paper_a = random.choices(pool, weights=weights, k=1)[0]
        used_in_batch.add(paper_a.id)

        # For paper B, prefer a different source type if possible (cross-source mixing)
        remaining = [(p, w) for p, w in available if p.id != paper_a.id]

        # Exclude pairs already seen in this run
        remaining = [(p, w) for p, w in remaining if _pair_key(paper_a.id, p.id) not in seen_pairs]

        diff_source = [(p, w) for p, w in remaining if p.source != paper_a.source]

        if diff_source and random.random() < 0.7:
            # 70% chance to pick cross-source matchup
            pool_b = [p for p, _ in diff_source]
            weights_b = [w for _, w in diff_source]
        else:
            pool_b = [p for p, _ in remaining]
            weights_b = [w for _, w in remaining]

        if not pool_b:
            used_in_batch.discard(paper_a.id)
            continue

        total_b = sum(weights_b)
        weights_b = [w / total_b for w in weights_b]
        paper_b = random.choices(pool_b, weights=weights_b, k=1)[0]
        used_in_batch.add(paper_b.id)

        pair = (paper_a.id, paper_b.id)
        batch.append(pair)
        seen_pairs.add(_pair_key(paper_a.id, paper_b.id))

    return batch


def _pair_key(id_a: str, id_b: str) -> tuple[str, str]:
    """Canonical (sorted) pair key so A-vs-B == B-vs-A."""
    return (min(id_a, id_b), max(id_a, id_b))
