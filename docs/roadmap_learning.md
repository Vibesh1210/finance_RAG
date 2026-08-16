# Learning roadmap — beyond M0

*Decided 2026-08-13 (DECISIONS.md #15). This supersedes the "stop at M0" commitment
(DECISIONS.md #9) with a **learning-optimized** selection of the later work. It is an
authority on WHICH post-M0 work is committed and in WHAT order; the execution plan and
design doc remain the authorities on HOW each piece is built.*

## Why this exists

The project has two equal goals: a working system **and** the human learning the domain
(DECISIONS.md #6). After M0, the choice of what to build next is now driven by **learning
value**, not product completeness. The target skill narrative:

> *"I built a RAG from data ingestion → hybrid retrieval → **reranking** → **GraphRAG**,
> instrumented it for **observability**, and can **evaluate any RAG pipeline on both
> performance and cost."*

Every item below is RAG-specific and advanced. The two biggest post-M0 phases are
**deliberately cut** because they teach little that transfers to RAG skills:

- **A web API (phase 6's API half)** — that's web engineering, not RAG. Observability is
  learned by instrumenting the pipeline directly (no server needed).
- **Embedder fine-tuning (phase 9)** — a specialized ML loop, and design-optional
  (decision-gated). Skipping it costs nothing on the RAG-skills axis.

Also deferred (not learning-dense enough right now, or cost/infra traps): news +
conversation + conflict-surfacing (phase 7 / part of 8), real-time market data, and the
full production hardening (phase 13).

## Mapping to the existing plan

| Learning item | Existing phase (subset used) | What we take |
|---|---|---|
| L1 · Observability + cost eval | Phase 6 (minus the API) | per-query tracing, cost/latency accounting |
| L2 · Reranker | Phase 8 (reranker only) | cross-encoder second pass + measured lift |
| L3 · GraphRAG POC | Phase 10 (POC scope) | a small entity/edge graph + one relational answer |
| L4 · Monitoring POC | Phase 12 (POC scope) | daily-filings watchlist alerts, dedup, precision/recall |

## The ordered plan

### Prerequisite — sign off M0 (days)
Run the verification pass (`learn/verification_guide.md`) + add the Tiingo key. This makes
the golden bank **frozen and trustworthy**, which is what lets every "did it improve?"
number below actually mean something. Tag `v0.1.0`.

### L1 — Observability + cost evaluation *(build this first)*
- **Goal:** see inside your own pipeline, and learn to evaluate a RAG on cost, not just
  quality.
- **Build:** instrument `answer()` to emit a trace per query — route + confidence,
  retrieval scores, SQL template + params, verifier verdict, **tokens, latency per stage,
  and a cost estimate**. A small CLI to run the golden bank and roll up per-stage cost +
  quality. No web API.
- **Learning payoff:** the transferable skill — "evaluate any RAG on performance *and*
  cost." First it's the measuring tool everything after it uses.
- **Honest note:** in this project the dollar cost is ~0 (free-tier Gemini + local models),
  so the interesting axis is **latency / compute budget** and the **methodology**. The
  method is identical when the costs are real.
- **Exit:** a trace file per query; a report showing quality *and* cost/latency per stage
  over the golden bank.

### L2 — Reranker (advanced retrieval)
- **Goal:** learn the "slow-but-smart second pass" and how to justify it with numbers.
- **Build:** a cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) over the fused top-20 →
  top-8, behind the existing retrieval interface (a config flag, so it's A/B-able).
- **Learning payoff:** measure its **lift** (does nDCG@8 / recall improve on the frozen
  golden bank?) **and its cost** (+ latency per query, via L1's tooling) — then decide if
  it's worth it. That decision *is* the skill.
- **Exit:** reranker on/off comparison on the golden bank: quality delta and latency delta,
  with a written go/no-go.

### L3 — GraphRAG POC
- **Goal:** answer a **relational** question that hybrid + SQL structurally cannot.
- **Build (POC scope, not production):** a small entity/edge graph — a handful of real,
  provenance-carrying relationships (e.g. WMT–COST peers, CAT–DE peers, NVDA→hyperscaler
  exposure), seeded/extracted from the filings with the source snippet on each edge. A
  simple traversal that returns the subgraph + evidence.
- **Learning payoff:** *why and when* a graph earns its place; the meta-skill of proving a
  technique is (or isn't) needed on your data.
- **Exit:** one golden "exposure/peer" question answered with edge provenance in the
  citation — something M0 correctly refuses today.

### L4 — Monitoring POC
- **Goal:** the proactive mode + event-driven design + alert quality.
- **Build (POC scope):** a watchlist + a monitor over the **daily filings feed we already
  have** (material 8-Ks by item code), with dedup and cited alerts. **Real-time market data
  is deferred** (licensed/expensive — the cost trap; EOD/filings only).
- **Learning payoff:** event-driven systems, deduplication, and alert **precision/recall**
  (a monitor that cries wolf is worse than none).
- **Exit:** a watchlist produces material, non-duplicate, cited alerts from fixture events,
  scored for precision/recall.

## Effort & the honest caveats

- **Rough total: ~6–8 weeks** at a learning pace (vs. ~4–5 months for the full product) —
  because the calendar-burning parts (real-time data, fine-tuning, full hardening) are cut.
- **Eval integrity is the one hard dependency:** freeze/verify the golden bank (the M0
  verification) before quoting any reranker/graph "lift" as a result.
- **Cross-cutting learning goal — "evaluate any RAG":** performance eval already exists
  (recall@10, MRR, nDCG, exact-match, look-ahead, Phase 3); L1 adds the **cost/latency**
  half; L2 is the case study that joins them.

## Relationship to the committed record

- Supersedes DECISIONS.md #9 (which committed to stopping at M0).
- Uses subsets of phases 6, 8, 10, 12; **does not** build the API (phase 6 remainder),
  sources v2 / conversation / conflicts (phase 7 / part of 8), fine-tune (phase 9),
  multi-hop agentic (phase 11), or full hardening (phase 13).
- The execution plan and design doc remain the build/design authorities for each subset.
