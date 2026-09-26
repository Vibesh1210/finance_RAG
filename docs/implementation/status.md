# Status — where the project is right now

State only; never an authority on design or plan. Updated at every step change and
whenever a blocker changes (ADR-0007). Last updated: **2026-09-26**.

## The steps

| # | Step | What it is | Status |
|---|---|---|---|
| — | **M0** (phases 0–5) | The first working version: data, search, numbers, answering | ✅ built; gates 0, 1, 4, 5 green; 2 at 5/9, 3 at 4/5 (human items) |
| 1 | **M0 sign-off** | You check the answer key against the filings; Tiingo key; freeze baselines; tag `v0.1.0` | ⏳ 0 / 159 checklist items ticked |
| 2 | Showcase 1 — README | Front page with real numbers | ⏳ after sign-off |
| 3 | **L1** — observability, cost, answer grading | Trace per question; quality + cost report; LLM judge for prose | ▶ **next to build** (in parallel with sign-off; scores stay provisional until then) |
| 4 | Showcase 2 — demo page + video | Local page over `answer()` | ⏳ after L1 |
| 5 | L2 — chunking evaluation | Quote-level answer key; four chunk-size variants | ⏳ |
| 6 | L3 — reranker | Cross-encoder second pass, on/off, measured | ⏳ |
| 7 | L4 — GraphRAG proof of concept | Small relationship graph with sources | ⏳ |
| 8 | L5 — monitoring proof of concept | Alerts on new filings, deduplicated | ⏳ |

Plan and specs: [roadmap.md](roadmap.md). What M0 contains: [completed/m0_phases_0-5.md](completed/m0_phases_0-5.md).

## What's loaded

389 filings (350 downloaded, 39 metadata-only baselines) · 41,175 facts · 405 restatement
links · 100 fiscal-calendar rows · 7,033 chunks, all embedded · prices: none ·
press-release (U13) rows: 63 staged (AAPL, CAT, COST), 0 loaded.

## Scores (provisional — answer key not yet human-checked; do not quote)

Quant exact-match 17/18 (the miss: CAT Q4 — derived exact value vs rounded press-release
gold) · refusals 10/10 · numbers cited 100% · look-ahead leaks 0 · router 60/60 ·
retrieval recall@10: fused 0.71, dense 0.63, sparse 0.15.

## Blockers and open items

**Yours (all in [m0_signoff_checklist.md](m0_signoff_checklist.md)):**
- 20 spot-check figures → `fixtures/spot_checks.json` (gate 2 check 2)
- Verify the staged U13 rows, then they're loaded (gate 2 check 7)
- Countersign the JNJ/Kenvue restatement (gate 2 check 9)
- Tiingo key in `.env` (gate 2 check 5)
- Review the metric registry; confirm the golden bank

**Engineering housekeeping (mine):**
- Docker Desktop was not running on 2026-09-26 — nothing that needs the database has been
  re-run since the doc restructure.
- CI risks: empty CI database, `pyyaml` not declared, bge-m3 not installed in CI
  ([03_evaluation_and_testing.md §6](../production/03_evaluation_and_testing.md)).
- U13 extraction covers only 3 of 10 companies (free-tier quota).
- `.serena/` (editor tool config) is committed; consider gitignoring it.

## Recent changes

- **2026-09-26** — docs restructured into `docs/production`, `docs/learning_docs`,
  `docs/implementation` (ADR-0019); `DECISIONS.md` became ADRs; the never-written corpus
  selection decision recorded as ADR-0020.
- 2026-09-17 — doc consolidation (ADR-0018); chunking eval and answer grading added to
  the roadmap (ADR-0016, ADR-0017).
- 2026-08-16 — M0 gate green (7/7).

Full build history: `git log`, and the archived execution plan.
