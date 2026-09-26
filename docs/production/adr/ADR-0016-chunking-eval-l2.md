# ADR-0016: Chunking evaluation added as L2

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-17 |
| **Type** | Scope |

## Context

Retrieval is graded at (filing, section) level: `eval/harness.py` collapses chunks to `(accession, section)` keys, so any chunk from the right section counts as a hit. The chunk sizes (~800 tokens / ~100 overlap) were never measured; real chunks run to 1,634 tokens.

## Decision

Add L2 after observability and before the reranker: a quote-level answer key (`golden/snippets_v0.yaml`, additive), chunk-level metrics (answer-hit@k, split answers), and a side-by-side chunk-size experiment. Renumbering: reranker L3, GraphRAG L4, monitoring L5.

## Consequences

The reranker will be measured at both section and quote level. Chunk parameters stand unless L2's written decision changes them.
