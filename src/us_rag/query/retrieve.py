"""Hybrid narrative retrieval (design §6.1).

    dense (bge-m3 / pgvector HNSW, cosine, top-50)
  + sparse (Postgres FTS, ts_rank_cd, top-50)
  → Reciprocal Rank Fusion (k=60) → top-20

The as-of filter is a HARD pushdown in BOTH legs (`knowledge_time <= :as_of`), never a
post-filter: no chunk newer than the question's as-of date can reach the caller. This is
the point-in-time guarantee the look-ahead gate (§9) enforces in CI. `as_of` is a
required keyword — there is no silent default, so a caller can never *forget* to be
point-in-time correct.

Reranking (cross-encoder over the fused top-20) is deferred to M1/Phase 8; this is the
M0 retriever.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import psycopg

RRF_K = 60          # reciprocal-rank-fusion constant (design §6.1)
LEG_K = 50          # each leg returns its top-50 before fusion
DEFAULT_TOP_K = 20  # fused output size handed to generation


@dataclass
class Hit:
    """One fused result, carrying enough to cite and to debug the fusion."""

    chunk_id: int
    accession: str
    company_id: int
    doc_type: str
    section: str
    knowledge_time: datetime
    text: str
    rrf_score: float
    dense_rank: int | None  # 1-based rank in the dense leg, or None if it missed
    sparse_rank: int | None


# ---- query embedding (bge-m3, loaded once, CPU-safe — mirrors ingest defaults) ----

_model = None


def _embedder():
    """Lazily load bge-m3 once and reuse it. Same CPU-safe defaults as the ingestion
    backfill (DECISIONS.md #11) so query and corpus vectors come from one config."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # heavy import, on purpose

        device = os.environ.get("US_RAG_EMBED_DEVICE", "cpu")
        _model = SentenceTransformer("BAAI/bge-m3", device=device)
        _model.max_seq_length = int(os.environ.get("US_RAG_EMBED_MAXLEN", "2048"))
    return _model


def embed_query(text: str) -> list[float]:
    vec = _embedder().encode([text], normalize_embeddings=True)[0]
    return [float(v) for v in vec]


# ---- the two legs (identical as-of pushdown) ----


def _company_clause(company_ids: Iterable[int] | None) -> tuple[str, list]:
    ids = list(company_ids) if company_ids else []
    return (" AND company_id = ANY(%s)", [ids]) if ids else ("", [])


def dense_leg(
    conn: psycopg.Connection,
    query_vec: Sequence[float],
    as_of: datetime | date,
    *,
    k: int = LEG_K,
    company_ids: Iterable[int] | None = None,
) -> list[int]:
    """Top-k chunk_ids by cosine distance, filtered to knowledge_time <= as_of."""
    extra, params = _company_clause(company_ids)
    literal = "[" + ",".join(f"{v:.7f}" for v in query_vec) + "]"
    rows = conn.execute(
        "SELECT chunk_id FROM chunks"
        " WHERE knowledge_time <= %s" + extra + " AND embedding IS NOT NULL"
        " ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s",
        [as_of, *params, literal, k],
    ).fetchall()
    return [r[0] for r in rows]


def sparse_leg(
    conn: psycopg.Connection,
    query: str,
    as_of: datetime | date,
    *,
    k: int = LEG_K,
    company_ids: Iterable[int] | None = None,
) -> list[int]:
    """Top-k chunk_ids by Postgres full-text rank, filtered to knowledge_time <= as_of."""
    extra, params = _company_clause(company_ids)
    rows = conn.execute(
        "SELECT chunk_id FROM chunks"
        " WHERE knowledge_time <= %s"
        "   AND tsv @@ websearch_to_tsquery('english', %s)" + extra +
        " ORDER BY ts_rank_cd(tsv, websearch_to_tsquery('english', %s)) DESC, chunk_id"
        " LIMIT %s",
        [as_of, query, *params, query, k],
    ).fetchall()
    return [r[0] for r in rows]


# ---- fusion ----


def rrf_fuse(
    rankings: Sequence[Sequence[int]], *, k: int = RRF_K, top_k: int = DEFAULT_TOP_K
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion. Each list contributes 1/(k + rank) per item (rank 1-based);
    scores sum across lists. Ties break by chunk_id so output is deterministic."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered[:top_k]


# ---- orchestration ----


def retrieve(
    conn: psycopg.Connection,
    query: str,
    *,
    as_of: datetime | date,
    top_k: int = DEFAULT_TOP_K,
    company_ids: Iterable[int] | None = None,
) -> list[Hit]:
    """Hybrid retrieve: run both legs at top-50, fuse to top_k, hydrate metadata.

    `as_of` is required — every retrieval in the system is point-in-time (design §6.5)."""
    query_vec = embed_query(query)
    dense = dense_leg(conn, query_vec, as_of, company_ids=company_ids)
    sparse = sparse_leg(conn, query, as_of, company_ids=company_ids)

    dense_rank = {cid: i for i, cid in enumerate(dense, start=1)}
    sparse_rank = {cid: i for i, cid in enumerate(sparse, start=1)}

    fused = rrf_fuse([dense, sparse], top_k=top_k)
    if not fused:
        return []

    ids = [cid for cid, _ in fused]
    meta = {
        row[0]: row
        for row in conn.execute(
            "SELECT chunk_id, accession, company_id, doc_type, section, knowledge_time, text"
            " FROM chunks WHERE chunk_id = ANY(%s)",
            [ids],
        ).fetchall()
    }
    hits = []
    for cid, score in fused:
        m = meta[cid]
        hits.append(
            Hit(
                chunk_id=m[0],
                accession=m[1],
                company_id=m[2],
                doc_type=m[3],
                section=m[4],
                knowledge_time=m[5],
                text=m[6],
                rrf_score=score,
                dense_rank=dense_rank.get(cid),
                sparse_rank=sparse_rank.get(cid),
            )
        )
    return hits
