"""Phase 3 eval harness: score a retrieval strategy over the factual golden bank, and
compare fused vs single-leg (the gate's "RRF beats each leg" sanity — execution plan).

A *retriever function* maps a question to a ranked list of distinct passage keys; the
harness is decoupled from retrieval internals (so it is unit-testable with a stub) and
ships three real ones — fused / dense-only / sparse-only — backed by the live store.

Baselines live in golden/thresholds.yaml and ratchet UP only: a metric below its
recorded baseline fails the gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from us_rag.eval.golden import Question
from us_rag.eval.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from us_rag.query.retrieve import (
    DEFAULT_TOP_K,
    LEG_K,
    dense_leg,
    embed_query,
    retrieve,
    sparse_leg,
)

# question -> ranked list of distinct (accession, section) keys, best first
RetrieverFn = Callable[[Question], list[tuple[str, str]]]


@dataclass
class BankResult:
    n: int
    recall_at_10: float
    mrr: float
    ndcg_at_10: float

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "recall_at_10": round(self.recall_at_10, 4),
            "mrr": round(self.mrr, 4),
            "ndcg_at_10": round(self.ndcg_at_10, 4),
        }


def _dedup(keys) -> list:
    seen: set = set()
    out: list = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def run_factual(questions: list[Question], retriever: RetrieverFn, *, k: int = 10) -> BankResult:
    """Score the answerable factual questions (those carrying gold passages). Abstain /
    typed-refusal behaviour is a separate behavioural check for later phases."""
    scored = [q for q in questions if q.kind == "factual" and q.gold]
    if not scored:
        raise ValueError("no answerable factual questions to score")
    rec = mrr = ndcg = 0.0
    for q in scored:
        ranked = retriever(q)
        rec += recall_at_k(ranked, q.gold_keys, k) or 0.0
        mrr += reciprocal_rank(ranked, q.gold_keys)
        ndcg += ndcg_at_k(ranked, q.gold_keys, k) or 0.0
    n = len(scored)
    return BankResult(n, rec / n, mrr / n, ndcg / n)


# ---- retriever functions backed by the live store ----


def _company_ids(conn, ticker: str | None):
    if not ticker:
        return None
    from us_rag.entities import resolve_one

    return [resolve_one(conn, ticker).company_id]


def _keys_for(conn, chunk_ids: list[int]) -> list[tuple[str, str]]:
    if not chunk_ids:
        return []
    rows = {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            "SELECT chunk_id, accession, section FROM chunks WHERE chunk_id = ANY(%s)",
            [chunk_ids],
        ).fetchall()
    }
    return _dedup([rows[c] for c in chunk_ids if c in rows])


def fused_retriever(conn) -> RetrieverFn:
    def fn(q: Question) -> list[tuple[str, str]]:
        hits = retrieve(
            conn, q.question, as_of=q.as_of, top_k=DEFAULT_TOP_K,
            company_ids=_company_ids(conn, q.company),
        )
        return _dedup([(h.accession, h.section) for h in hits])

    return fn


def dense_retriever(conn) -> RetrieverFn:
    def fn(q: Question) -> list[tuple[str, str]]:
        ids = dense_leg(
            conn, embed_query(q.question), q.as_of, k=LEG_K,
            company_ids=_company_ids(conn, q.company),
        )
        return _keys_for(conn, ids)

    return fn


def sparse_retriever(conn) -> RetrieverFn:
    def fn(q: Question) -> list[tuple[str, str]]:
        ids = sparse_leg(
            conn, q.question, q.as_of, k=LEG_K, company_ids=_company_ids(conn, q.company)
        )
        return _keys_for(conn, ids)

    return fn


# ---- thresholds: ratchet-up only ----


def load_thresholds(path: str | Path) -> dict:
    p = Path(path)
    return (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}


def check_ratchet(name: str, result: BankResult, thresholds: dict) -> list[str]:
    """Regressions against recorded baselines (empty list = ok). Baselines only move up;
    a metric below its baseline is a gate failure."""
    base = thresholds.get(name, {}) or {}
    fails = []
    for metric in ("recall_at_10", "mrr", "ndcg_at_10"):
        b = base.get(metric)
        v = getattr(result, metric)
        if b is not None and v + 1e-9 < b:
            fails.append(f"{name}.{metric} {v:.4f} < baseline {b:.4f}")
    return fails
