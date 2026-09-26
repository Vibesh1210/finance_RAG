# ADR-0011: Embedding backfill memory-bounded for an 8 GB laptop

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-31 |
| **Type** | Operations |

## Context

Embedding 7,033 chunks crashed after ~320 on an Apple M2 with 8 GB. sentence-transformers defaulted to the GPU, whose memory is the same 8 GB the display uses.

## Decision

Default to `device="cpu"`, `batch_size=8`, `max_seq_length=2048`. The cap was chosen from data: all chunks were tokenised; the longest is 1,634 tokens (p99 1,307), so 2,048 truncates none (1,024 would have truncated 503). Overridable via `US_RAG_EMBED_DEVICE` / `US_RAG_EMBED_BATCH` / `US_RAG_EMBED_MAXLEN`.

## Consequences

Slower but predictable. Query-time embedding (`query/retrieve.py`) uses the same settings so query and corpus vectors come from one configuration.
