# Status — where the project is right now

State only; never an authority on design or plan. Updated at every step change and
whenever a blocker changes (ADR-0007). Last updated: **2026-09-27**.

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

**Known correctness bugs (found 2026-09-27; fix as a small step after E1, before L1):**
- **Margin rendered as dollars, uncited.** "What was Apple's gross margin for fiscal year
  2025?" routes to the numbers lane; `derived_margin` returns a ratio (0.469…), which
  `_as_reported` formats as `$0 million`, and the answer carries no citation (derived
  results have none). Confirmed by running `_as_reported(Decimal("0.4690516"), "ratio")`.
  Not caught by gate 5 (no golden question asks a margin through `answer()`).
- **Unsupported intent answered as a different question.** "Apple's revenue *growth* for
  FY2025" routes to the numbers lane and returns total revenue — `extract_metric_key`
  ignores "growth". Confirmed via `classify` + `extract_metric_key`.
- **To confirm with the database** (from `frontend/docs/interview_ui_design.md` §14):
  `metric_value`'s `exact or rows` fallback can return a year-to-date value under a quarter
  label; Q4 answers cite only the FY filing, not all four inputs; a comparison whose every
  leg abstains still returns status `answered`.

**Engineering housekeeping (mine):**
- Additional isolated reproduction on 2026-09-27 confirms the quarter/YTD fallback
  defect with synthetic H1-only input; the growth dispatch and margin answer failures
  were also reproduced through `_metric_answer`. Live-corpus checks remain pending.
- PostgreSQL remains unavailable on 2026-09-26. After the backend/frontend directory
  split, 99 database-independent tests pass; 37 database tests were not run. Gate 0
  passes four checks and fails only the database connection check. Compose configuration,
  package/data paths, the dependency lockfile, and current documentation links validate.
- CI risks: empty CI database, `pyyaml` not declared, bge-m3 not installed in CI
  ([03_evaluation_and_testing.md §6](../production/03_evaluation_and_testing.md)).
- U13 extraction covers only 3 of 10 companies (free-tier quota).
- `.serena/` (editor tool config) is committed; consider gitignoring it.

## Recent changes

- **2026-09-27** — UI review incorporated into a [reduced v1 proposal](../../frontend/docs/interview_ui_v1.md):
  three simple pages, a curated J&J comparison, and video backup. Extended design retained
  as reference; Streamlit preferred but framework choice remains open. Known numeric
  answer defects documented in the answering LLD; application code unchanged.
- **2026-09-26** — backend code, tests, database definitions, gates, and scripts moved
  under `backend/`; UI design moved to `frontend/docs/`. Root commands/configuration and
  shared datasets retained; path updates recorded in ADR-0022. No frontend implemented.
- **2026-09-26** — [Interview UI design proposal](../../frontend/docs/interview_ui_design.md)
  prepared for review: three core pages (Query & Evidence, Metrics & Evaluations,
  Architecture with HLD/LLD) plus Data Explorer and Time Travel. No UI implemented;
  stack and scope expansion remain proposed, and the roadmap order is unchanged.
- **2026-09-26** — docs restructured into `docs/production`, `docs/learning_docs`,
  `docs/implementation` (ADR-0019); `DECISIONS.md` became ADRs; the never-written corpus
  selection decision recorded as ADR-0020.
- 2026-09-17 — doc consolidation (ADR-0018); chunking eval and answer grading added to
  the roadmap (ADR-0016, ADR-0017).
- 2026-08-16 — M0 gate green (7/7).

Full build history: `git log`, and the archived execution plan.
