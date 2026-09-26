# ADR-0015: Post-M0 scope is a learning-optimised selection

| | |
|---|---|
| **Status** | Accepted (amended by ADR-0016, ADR-0017) |
| **Date** | 2026-08-13 |
| **Type** | Scope |

## Context

After M0 the remaining original phases mixed RAG-specific skills with generic web engineering and side-quests.

## Decision

Pursue a learning-focused roadmap (`docs/implementation/roadmap.md`): observability and cost, reranker, GraphRAG proof of concept, monitoring proof of concept. Deliberately cut: web API, embedder fine-tuning, news/conversation/conflict surfacing, multi-hop agent, real-time market data, full hardening.

## Consequences

Supersedes ADR-0009. M0 verification is still required first so later "lift" numbers are trustworthy.
