# Completed — M0, phases 0–5

M0 ("milestone zero") is the first working version: questions in, cited answers or honest
refusals out. It was built in six phases between 2026-07-10 and 2026-08-16 (last code
commit "M0 Done"). The full original spec for each phase is in
`archive/execution_plan_us.md`, Part II; this file records what was actually delivered.

```
Phase 0 rails ─► Phase 1 data spine ─► Phase 2 ingestion ─► Phase 3 eval + search ─► Phase 4 numbers ─► Phase 5 answering = M0
```

| Phase | Delivered | Gate now | Decisions |
|---|---|---|---|
| **0 · Rails** | Repo layout, Docker Postgres + pgvector (port 5433), Makefile, CI, gate runner, frozen SEC ticker snapshot, derived `universe.json` | 5/5 | ADR-0001–0004 |
| **1 · Data spine** | Schema (migration 001), append-only trigger, as-of reader, units normaliser, fiscal resolver + seeds, entity resolution; 50 tests at the time | 8/8 | ADR-0005, 0010 |
| **2 · Ingestion** | EDGAR client + backfill (389 filings), facts load (41,175 facts, 405 supersession links, 100 calendar rows), narrative (7,033 chunks, embedded), U13 extractor (63 rows staged), price loader (not run) | 5/9 — 4 human/key items | ADR-0008, 0011, 0012, 0020 |
| **3 · Eval + search** | Golden bank (40 factual + 20 quant), retrieval metrics + harness, hybrid retriever (dense + keyword + RRF, as-of pushdown), look-ahead scan | 4/5 — baseline not frozen | ADR-0012 |
| **4 · Numbers** | Metric registry (12 metrics, JPM abstentions), migration 003 + read-only role, `metric_value/series/compare`, YoY/CAGR/margin/TTM, Q4 derivation, segment executor (no data), verifier, `execution_v0` (25) | 6/6 | ADR-0013 |
| **5 · Answering** | Rule-based router, `answer()` (route → fetch → write → verify), typed refusals, clarifications, posture line, opt-in Gemini prose | 7/7 = **M0 reached** | ADR-0014 |

## M0 gate results (provisional)

| Criterion | Bar | Result |
|---|---|---|
| Quant exact-match (answerable) | ≥ 90% | 17/18 = 94% (miss: CAT Q4 — derived exact vs rounded press-release gold) |
| Typed refusal on unanswerables | 100% | 10/10 |
| Every emitted number cited | 100% | 100% |
| Look-ahead leaks | 0 | 0 |
| JPM: revenue caveated, gross margin not answered | yes | yes |
| Router accuracy (baseline) | ≥ 0.85 | 60/60 |

Provisional because the answer keys were drafted from the loaded data and have not been
checked by a human. Closing that is step 1 of the roadmap (M0 sign-off).

## What M0 deliberately does not do

Segment numbers via SQL (ADR-0013), prices (no key), preliminary figures (awaiting
verification), the `hybrid` merge, verification of numbers inside model-written prose,
and everything in [../future_scope.md](../future_scope.md). The full design-vs-build list
is in `docs/production/02_hld.md` §8.
