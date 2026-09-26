# LLD · Retrieval

`src/us_rag/query/retrieve.py`. Hybrid search over `chunks`, point-in-time by
construction.

## 1. Pipeline

```
query text, as_of, [company_ids]
   │
   ├─ embed_query ── bge-m3 (same config as ingestion, ADR-0011) ──► 1024-d vector
   │
   ├─ dense_leg ─── ORDER BY embedding <=> :vec, chunk_id          ─┐
   │                WHERE knowledge_time <= :as_of [AND company]     │  top-50 each
   │                                                                 │
   ├─ sparse_leg ── WHERE tsv @@ websearch_to_tsquery(:q)           │
   │                ORDER BY ts_rank_cd DESC, chunk_id               │
   │                WHERE knowledge_time <= :as_of [AND company]    ─┘
   │
   ├─ rrf_fuse ──── score(chunk) = Σ over legs 1 / (60 + rank)  → sort, ties by chunk_id → top_k (default 20)
   │
   └─ hydrate ───── Hit(chunk_id, accession, company_id, doc_type, section,
                        knowledge_time, text, rrf_score, dense_rank, sparse_rank)
```

`answer()` asks for `top_k=8`.

## 2. Point-in-time guarantee

The as-of filter is a **pushdown** inside both SQL queries, not a filter applied to
results afterwards, so a future chunk can never be ranked, fused or returned. `as_of` is a
required keyword argument with no default.

A `date` as-of is compared as that date at 00:00 UTC (Postgres casting); the look-ahead
scan (`eval/lookahead.py:to_cutoff`) mirrors that exactly.

## 3. Parameters

| Constant | Value | Source |
|---|---|---|
| `LEG_K` | 50 | design §6.1 |
| `RRF_K` | 60 | design §6.1 |
| `DEFAULT_TOP_K` | 20 | design §6.1 |
| Distance | cosine (`<=>`, HNSW `vector_cosine_ops`) | design §6.1 |
| Text search config | `english`, `websearch_to_tsquery`, `ts_rank_cd` | design §6.1 |

## 4. Known behaviour

- **Sparse leg is weak.** `websearch_to_tsquery` ANDs every word, so long natural
  questions often match nothing. Measured (provisional): sparse recall@10 0.15 vs dense
  0.63 vs fused 0.71. Pivot P-US-8 (a BM25 engine) exists if it drags fusion below dense.
  Not tuned until the golden bank is frozen.
- **No reranker yet.** A cross-encoder over the fused top-20 is L3.
- **Grading granularity.** The eval collapses hits to `(accession, section)`, so any chunk
  in the right section scores (ADR-0016; fixed by L2).
- **Company filter** comes from the router's detected tickers; a question naming no
  company searches all ten.
