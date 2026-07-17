# STATUS — read this first

Global state file for any AI or human picking up this repo. Maintained per
DECISIONS.md #7: updated at every phase transition and whenever blockers change.
The active phase's theory-to-code deep dive lives in `CURRENT_PHASE.md`.

## What this project is

A financial question-answering system (RAG) over **10 US public companies**
(AAPL, CAT, COST, DE, JNJ, JPM, MSFT, NVDA, WMT, XOM), corpus window
**FY2024 + FY2025 per each company's own fiscal calendar**, built from SEC
filings (10-K/10-Q/8-K), XBRL structured facts, and Tiingo market data.

Two goals, weighted equally (DECISIONS.md #6): the working system, AND the
human learning the domain. Every phase ships learning material in `learn/`.

Core invariants (violations fail gates — full list in CLAUDE.md):
- Bitemporal, append-only facts: "what did we know, when" is always answerable.
- Fiscal periods resolved from `fiscal_calendars`, never computed by formula.
- No LLM arithmetic — every number in an answer comes from SQL/deterministic code.
- EDGAR fair-access rules hard-coded; CI is fixtures-only (no live API calls).

Authority order: `docs/execution_plan_us.md` (build order) > `docs/design_us.md`
(design) > this file (state summary only — never an authority on design).

## Phase map

| Phase | What | Status |
|---|---|---|
| 0 | Scaffold, docker (pgvector), CI, gate rails, universe | ✅ done, gate green |
| 1 | Data spine: schemas, bitemporal facts, units, fiscal, identity | ✅ done, gate green |
| **2** | **Ingestion: EDGAR client, facts, narrative, U13, prices** | **⟵ CURRENT — not started** |
| 3 | Eval harness, golden bank (60 Qs), hybrid retrieval, look-ahead gate | ⏳ |
| 4 | SQL branch: metric mappings, template compiler, read-only executor | ⏳ |
| 5 | Router, generation, verification → **M0** | ⏳ |
| 6 | API, tracing, cost accounting, supersession-aware cache | ⏳ |
| 7 | Sources v2: news + prepared remarks (M1 part A) | ⏳ |
| 8 | Quality layer: reranker, conversation, conflicts → **M1 gate** | ⏳ |
| 9 | Embedder fine-tune + shadow-index migration drill (M1 complete) | ⏳ |
| 10 | Graph layer (**M2** — decision-gated) | ⏳ |
| 11 | Multi-hop agentic research (**M3**) | ⏳ |
| 12 | Monitoring agents (**M4**) | ⏳ |
| 13 | Hardening (**M5** subset) | ⏳ |

## Current state (updated 2026-07-17)

- Phases 0–1 complete and committed; working tree clean; `make gates` green.
- Phase 2 not started. Deep dive written: see `CURRENT_PHASE.md`.
- DB schema (`db/migrations/001_core.sql`) already has every table Phase 2
  loads into: `documents`, `facts` (+ append-only trigger), `fiscal_calendars`,
  `chunks`, `prices`, `corporate_actions`.

### Blockers / open [HUMAN] items

- `.env`: `TIINGO_API_KEY` **empty** (free registration at tiingo.com) — needed
  for Phase 2d prices.
- `.env`: `ANTHROPIC_API_KEY` **empty** — needed for Phase 2e headline extraction.
- Phase 2 [HUMAN] work (~3.5 h): spot-verify 20 facts → `fixtures/spot_checks.json`;
  verify all ~80 U13 rows; curate IR prepared-remarks manifest (best-effort).

## How to verify state

```
make gates          # all completed phase gates must stay green
make gate PHASE=N   # run one phase's gate
```

Deviations and pinned interpretations: `DECISIONS.md` (7 entries).
Per-phase technical writeups: `phases_docs/`. Learning track: `learn/README.md`.
