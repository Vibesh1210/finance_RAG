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

**Committed target (DECISIONS.md #15, supersedes #9):** ship **M0** (Phase 5), then a
**learning-focused** selection — L1 observability+cost eval, L2 reranker, L3 GraphRAG POC,
L4 monitoring POC (`docs/roadmap_learning.md`). Cut: web API, fine-tune, news/conversation,
real-time data, full hardening.

| Phase | What | Status |
|---|---|---|
| 0 | Scaffold, docker (pgvector), CI, gate rails, universe | ✅ done, gate green |
| 1 | Data spine: schemas, bitemporal facts, units, fiscal, identity | ✅ done, gate green |
| 2 | Ingestion: EDGAR client, facts, narrative, U13, prices | gate 5/9 — 4 [HUMAN]/[KEY] items open (DECISIONS #12) |
| 3 | Eval harness, golden bank (60 Qs), hybrid retrieval, look-ahead gate | gate 4/5 — recall baseline pending [HUMAN] verify + freeze |
| 4 | SQL branch: metric mappings, template compiler, read-only executor | gate 6/6 GREEN (execution_v0 golds [HUMAN]-provisional; registry review pending) |
| 5 | Router, generation, verification → **M0** | ✅ **gate GREEN 7/7 — M0 REACHED** (golds [HUMAN]-provisional) |
| 6–9 | API/cache · news+remarks · reranker/conversation · fine-tune (M1) | 🧊 polish — opt-in after M0 |
| 10–13 | Graph · multi-hop · monitoring · hardening (M2–M5) | 🧊 shelved (DECISIONS.md #9) |

## Current state (updated 2026-07-31)

- Phases 0–1 complete; **all three gates re-run green on 2026-07-31**
  (`phase_00` 5/5, `phase_01` 8/8). Phase 2 work is still **uncommitted**.
- Phase 2 code fully written (`db/migrations/002_ingest.sql`, six modules under
  `src/us_rag/ingest/`, five test files, `scripts/freeze_phase02_fixtures.py`).
- **`gates/phase_02.py` now written** — nine checks mapped 1:1 to the execution
  plan. Live result: **5 PASS, 4 blocked** (checks 2/5/7/9 — the [HUMAN]/[KEY]
  items below). The gate is the checklist; run `make gate PHASE=2`.
- EDGAR backfill: **389 documents** (350 with blobs, 39 metadata-only),
  **41,175 facts**, **405 supersession links**, `fiscal_calendars` complete
  (100 rows, XBRL-confirmed).
- Narrative: **7,033 chunks, embeddings 100% complete** (memory-fixed backfill,
  DECISIONS.md #11 — was OOM'ing the M2/8 GB GPU; now CPU, 2048-token cap). The
  retrieval substrate is ready: pgvector HNSW (dense) + tsvector (sparse) +
  `chunks_asof_idx` on (company_id, knowledge_time) for the point-in-time pushdown.
- **Phase 3 in progress:** hybrid retriever (`query/retrieve.py` — dense+sparse+RRF,
  as-of hard-pushdown) and eval harness (`eval/` — recall@10/MRR/nDCG@10, golden
  loader, fused/dense/sparse runners, ratchet-up thresholds) **built + unit-tested**
  (18 tests). Remaining: draft the 60-question golden bank (I draft, [HUMAN] verifies),
  the look-ahead gate, and `gates/phase_03.py`. Observation to revisit *after* the bank
  is frozen (measure-before-tune): the sparse leg returns thin/empty results on several
  queries (Postgres `websearch_to_tsquery` AND-semantics) — a known tuning knob.
- **Golden bank v0 drafted** (`golden/factual_v0.yaml` 40 + `golden/quant_v0.yaml` 20),
  grounded in real accessions/values/sections, matching the plan's distribution. First
  **unofficial** score (gold not yet [HUMAN]-verified, so NOT frozen): fused
  recall@10 **0.71** > dense 0.63 > sparse 0.15 — the "RRF beats each leg" sanity
  already holds. Weakest categories: cross_company 0.38, narrative 0.67 (sparse-leg
  weakness confirmed as the top post-verification tuning target).
- **`gates/phase_03.py` built — 4/5 green.** PASS: bank schema-valid + distribution,
  leakage lint, **look-ahead (zero leaks across 60 Qs, 6 historical-as-of samples with
  teeth)**, RRF-beats-each-leg. FAIL (pending): recall@10 ≥ baseline — waits on [HUMAN]
  verification of the 60 answers, then freezing `golden/thresholds.yaml`. That freeze is
  the last step to close Phase 3.
- **Phase 4 in progress — deterministic spine built.** Migration `003_metrics.sql`
  (nullable `us_gaap_tag` = typed abstention; registry unique indexes; **read-only role
  `usrag_ro`**). Registry seeded from `fixtures/metric_mappings.yaml` (12 metrics, 4
  revenue overrides, 2 JPM abstentions — [HUMAN] review pending, ~45 min). `query/metrics.py`:
  resolver (company-override > default, valid_from) + `metric_value` — exact number,
  as-of-correct (reuses `store.asof`), cited, or typed abstention; runs under `connect_ro`.
  Verified live: exact values cited; JPM gross-profit/cost-of-revenue abstain; JPM revenue
  caveated; pre-filing as-of abstains; read-only role blocks writes. Remaining Phase 4
  slices: series/compare, derived (TTM/YoY/CAGR/margin), segment facts, Q4 derivation,
  verifier v1, `execution_v0.yaml`, `gates/phase_04.py`.
- **Phase 4 slice 2 done — series/compare + derived.** `metric_series` (last-N periods),
  `metric_compare` (across companies, comparability-enforced — JPM flags the comparison
  non-comparable), and `derived_yoy` / `derived_cagr` / `derived_margin` — all computed in
  Decimal with a recorded computation string (no-LLM-arithmetic). Verified live: NVDA
  revenue YoY +114.2%, MSFT CAGR +14.9%, AAPL gross margin 46.9%, **JPM gross margin
  abstains** (gross_profit abstains → margin abstains). 8 metric unit tests.
- **Phase 4 slice 3 done — Q4 derivation + TTM.** `q4_value` (precedence: direct/U13
  preliminary row → balance-sheet = FY-end → additive derivation FY−Q1−Q2−Q3 with a
  period-tiling guard → else abstain; **non-additive/EPS never subtracted**), `quarter_value`,
  `derived_ttm` (additive-only; EPS abstains). Also hardened `metric_value` to disambiguate
  a Q4-duration fact from the FY fact by period_start (safe fallback — no regression).
  Verified live: **NVDA Q4 FY2025 revenue = 130,497 − 26,044 − 30,040 − 35,082 = 39,331M**
  (source=derived, cited to the 10-K) — the gate's Q4 test; Q4 EPS abstains; AAPL Q4
  total_assets = FY-end; TTM revenue = FY (sanity); TTM EPS abstains. 12 metric unit tests.
- **Phase 4 slice 4 (segment) — executor done, DATA GAP flagged.** `segment_value`
  (dimensional axis/member lookup, same registry/as-of machinery) is built and fails safe.
  **Blocker:** zero segment facts are loaded — Phase 2 used SEC `companyfacts` (company-level
  only); segment breakdowns live in the filings' dimensional XBRL, which was never extracted.
  Loading them needs a new dimensional-iXBRL pass over the blobs (a real ingestion task,
  error-prone). Note: the golden bank's 8 segment questions are ALSO retrieval-scored in
  Phase 3 (gold = Item 7 MD&A), so segment questions have a **narrative fallback for M0**.
  DECISION PENDING (user): (a) build segment-XBRL ingestion, or (b) rely on narrative
  fallback for M0 and defer segment-SQL. [RESOLVED: DECISIONS #13 — narrative fallback.]
- **Phase 4 slice 5 done — verifier v1.** `query/verify.py`: a claimed number passes only
  if it exactly matches the executor's value (full precision, with narrated-rounding
  tolerance), its citation is the authoritative accession, a non-comparable metric isn't
  claimed comparable, and derived numbers carry a computation record; a number emitted for
  an abstaining metric fails closed. Verified live: tampered value fails, wrong citation
  fails, a number on JPM gross-margin (abstains) fails, '0.47' for Apple's 0.4690… passes.
  8 verifier unit tests.
- **Phase 4 slice 6 done — `execution_v0.yaml` (25 SQL-path Qs) + `gates/phase_04.py` GREEN (6/6).**
  Gate checks: registry seeded (12 metrics + JPM abstentions); **execution_v0 exact-match
  25/25** (no tolerance); Q4 derivation (NVDA Q4 FY2025 = FY−ΣQ1–Q3, derived); JPM behaviors
  (revenue caveated, gross profit/margin abstain); no-LLM-arithmetic (derived carries a
  computation record, verifier enforces); segment fails safe (DECISIONS #13). 37 metric/eval
  unit tests total. **Phase 4 build complete.** [HUMAN] pending (~45 min, overlaps other
  verification): confirm the 25 execution_v0 golds + review `fixtures/metric_mappings.yaml`.
  Note: `make gates` still stops at `phase_02` (its [HUMAN] items) before reaching 3/4;
  run `make gate PHASE=3` / `PHASE=4` directly.
- **Phase 5 in progress — router done.** `query/router.py`: deterministic router (DECISIONS
  #14 — rule-based for M0, not an LLM classifier), entity+fiscal resolution before routing,
  typed routes (metric/narrative/graph/unanswerable/clarify/hybrid) + confidence + reason.
  Measured **100% (60/60)** against the golden bank (the design's router confusion matrix) —
  the recorded M0 baseline. `classify()` is pure (8 unit tests). Remaining Phase 5 slices:
  **generation** (LLM/Gemini over retrieved chunks + SQL results, the one model call site) +
  **verifier wiring** (mismatch → regenerate → abstain) + typed refusals + posture guard;
  then **`gates/phase_05.py` = the M0 gate** (full golden run).
- **Phase 5 DONE — M0 gate GREEN (7/7).** `query/generate.py`: `answer()` = route → fetch
  → generate → verify. Numbers are templated from the deterministic executor and
  verifier-checked; narrative is LLM-injectable (`gemini_generate`, opt-in — the gate is
  fixtures-only/model-free). M0 gate results: **quant exact-match 17/18 = 94%** (the one
  miss is CAT Q4 — derived exact vs rounded press-release gold; reconcile in verification);
  **100% typed abstention**; **every number cited**; ambiguities clarified; **zero
  look-ahead**; JPM caveated/abstains; **router 100%** baseline. Live end-to-end verified
  (metric, compare, refusal, clarify, and a real Gemini narrative answer with citations).
- **M0 status:** engineering-complete and gate-green **on [HUMAN]-provisional golds**. True
  M0 sign-off + `v0.1.0` tag awaits the verification pass (`learn/verification_guide.md`),
  which finalizes the golds behind Phases 2/3/4/5. Learning walkthroughs
  **`learn/phase_0[2-5].md` written** (plain-language + one self-checking exercise each,
  all four exercises verified solvable); `learn/README.md` syllabus updated 2→5 ✅.
- U13 (2e) extraction **ran**: ~80 rows staged in `fixtures/u13_staged.json`,
  **not yet loaded** — they insert only after human verification (DECISIONS.md #5).
- `prices` / `corporate_actions` still empty (2d) — `TIINGO_API_KEY` unset.

### Blockers / open items (= the 4 red gate checks + prices)

**All [HUMAN] verification is now one click-and-compare checklist:
`learn/verification_guide.md`** (~159 items, mostly number-matching, with as-reported values,
SEC filing links, and where to look). Covers spot-checks, golden bank, execution_v0, the
U13 rows, the registry review, the JNJ restatement countersign, and the Tiingo key.


Resolved since last update: Phase 1 quarter-band regression (DECISIONS.md #10,
band 83–111; `phase_01` green again); `GEMINI_API_KEY` now set (2e ran).

- **[KEY] gate 5 — prices:** `.env` `TIINGO_API_KEY` **empty** (free at tiingo.com),
  then run the 2d price backfill (NVDA June-2024 split must land).
- **[HUMAN] gate 2 — spot-checks:** fill the 20 slots in
  `fixtures/spot_checks.template.json` (value read from each filing by hand),
  save as `fixtures/spot_checks.json`. Template pre-slotted, 2/company.
- **[HUMAN] gate 7 — U13:** verify every row in `fixtures/u13_staged.json`
  against its 8-K Ex-99, then load them (`human_verified=true`).
- **[HUMAN] gate 9 — supersession:** countersign the JNJ/Kenvue case
  (`human_countersigned=true` in `fixtures/supersession_confirmed.json`).
- **[HUMAN, non-gating]** curate IR prepared-remarks manifest (U5, best-effort).

When the gate is green: archive `CURRENT_PHASE.md` → `learn/phase_02_brief.md` and
write the `learn/phase_02.md` walkthrough + exercise (CLAUDE.md learning loop).

## How to verify state

```
make gates          # all completed phase gates must stay green
make gate PHASE=N   # run one phase's gate
```

Deviations and pinned interpretations: `DECISIONS.md` (7 entries).
Per-phase technical writeups: `phases_docs/`. Learning track: `learn/README.md`.
