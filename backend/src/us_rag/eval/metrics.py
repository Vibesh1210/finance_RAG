"""Retrieval metrics for the factual golden bank (design §6.1, execution plan Phase 3).

Each operates on a ranked list of DISTINCT passage keys (accession, section) in
retrieval order, scored against the set of gold passage keys a human labelled. "@k"
means the top-k distinct passages. Pure functions — no DB, no model — so they run in
the fast suite and the numbers are reproducible.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence


def recall_at_k(ranked: Sequence[Hashable], gold: set, k: int = 10) -> float | None:
    """Fraction of gold passages present in the top-k. None when there is no gold
    (recall is undefined then; the runner skips those questions)."""
    if not gold:
        return None
    return len(set(ranked[:k]) & gold) / len(gold)


def reciprocal_rank(ranked: Sequence[Hashable], gold: set) -> float:
    """1 / rank of the first gold passage (1-based); 0.0 if none was retrieved."""
    for i, key in enumerate(ranked, start=1):
        if key in gold:
            return 1.0 / i
    return 0.0


def _dcg(relevances: Sequence[float]) -> float:
    # position i (0-based) is discounted by log2(i + 2): rank 1 -> /1, rank 2 -> /1.585, …
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(ranked: Sequence[Hashable], gold: set, k: int = 10) -> float | None:
    """Binary-relevance nDCG@k — rewards ranking gold passages nearer the top. None when
    there is no gold. The ideal ranking puts all min(|gold|, k) gold passages first."""
    if not gold:
        return None
    gains = [1.0 if key in gold else 0.0 for key in ranked[:k]]
    ideal = [1.0] * min(len(gold), k) + [0.0] * max(0, k - len(gold))
    idcg = _dcg(ideal)
    return _dcg(gains) / idcg if idcg > 0 else 0.0
