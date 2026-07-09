# Execution Plan — US Equity Financial RAG

**Status:** Draft v0.3 · 2026-07-10 (standalone rewrite: every phase fully specified here; no external plan required to build)
**Design authority:** `design_us.md` (this repo). That document and this plan are the complete doc set for the build.
**Self-containment rule:** The appendix compares this plan to the sibling Indian-market project — **informational only**, never required for building.

---

## Part 0 — Operating protocol

**Session protocol.** Each working session: read `CLAUDE.md`, read this plan's Phase N (the first phase whose gate is red), implement toward the gate, run `make gate PHASE=N`, keep **all previous gates green** (regression rule), commit as `phase-N: <what>`. A phase is done only when `gates/phase_NN.py` passes in CI.

**Gates are TDD at phase granularity.** Every phase defines its gate *before* implementation; gate scripts live in `gates/phase_00.py` … `gates/phase_13.py` and run fixtures-only (no network in CI — ever).

**DECISIONS.md.** Any deviation from a pin (U1–U13), any threshold change, any scope change = a dated DECISIONS.md entry: what, why, what it supersedes. Silent deviations are defects.

**`[HUMAN]` markers.** Tasks only the human can do (accounts, approvals, hand-verification). They are scheduled, bounded, and never on the critical path longer than necessary.

**Pivot triggers (Part III).** Known risks carry pre-decided pivots — when the signal fires, take the pivot and log it; don't relitigate under pressure.

### 0.1 Repo layout

```
US_rag/
  CLAUDE.md  DECISIONS.md  Makefile  docker-compose.yml  .env.example
  docs/          design_us.md, execution_plan_us.md (this file)
  src/           ingest/ (EDGAR client, facts, narrative, U13, prices)
                 store/  (schemas, bitemporal, fiscal, security master)
                 query/  (router, retrieval, sql_templates, verify, converse)
                 serve/  (API, tracing, cache)
  gates/         phase_00.py … phase_13.py
  evals/         golden/ (factual_v0.yaml, quant_v0.yaml, execution_v0.yaml), runners/, thresholds.yaml
  fixtures/      company_tickers.json (snapshot), spot_checks.json, unit/fiscal fixtures
  blobs/         raw artifacts by accession (gitignored)
```

### 0.2 Pinned decisions

| # | Decision | Pin | Rationale / trigger |
|---|---|---|---|
| U1 | Universe | AAPL, MSFT, NVDA, WMT, COST, JPM, XOM, JNJ, CAT, DE (design §1.2) | Sector + FYE diversity, graph pairs, JPM as mapping stressor. `[HUMAN]` approves before Phase 2. |
| U2 | Corpus window | FY2024 + FY2025 **per company's own fiscal calendar**, plus 8-Ks in span | Windows deliberately misalign across companies. |
| U3 | Filings source | EDGAR only, fair-access-compliant client; `SEC_EDGAR_USER_AGENT` env required | No third-party filing aggregators. |
| U4 | Structured numbers | XBRL `companyfacts` is ground truth; **statement-scale** PDF/vision parsing not built. Sole exception: the U13 headline extractor (human-gated) | Ex-99 is untagged — without U13, §4.2's preliminary rows can never exist. Vision fallback defined-but-dormant. |
| U5 | Transcripts | **Not in v0.** 8-K Ex-99.1 releases + IR-posted prepared remarks (manifest-fetched) | = design D-US-1. Revisit: ≥5 golden questions need Q&A content. |
| U6 | Market data | Tiingo EOD primary + Stooq fallback; unadjusted prices + actions table; adjust at query time. **Price answers split-adjusted only; total-return out of v0** | = design D-US-2, §4.7. yfinance rejected. Basis pinned, never implicit. |
| U7 | Identifiers | CIK primary, point-in-time ticker aliases, FIGI via OpenFIGI; **no CUSIP/ISIN** | Licensing (design §4.3). |
| U8 | Fiscal resolution | `fiscal_calendars` populated from XBRL contexts; **formula-computed quarter boundaries forbidden** (lint-enforced) | design §4.6 — the most bug-prone area of the build. |
| U9 | Embedding model | `BAAI/bge-m3`, local | Swap seam to `bge-base-en-v1.5` (design D-US-5). |
| U10 | Segment scope | Business-segment axis only (no geo); NVDA, AAPL, MSFT at minimum | = design D-US-3. |
| U11 | Supersession policy | **Row-level bitemporal**: every row keeps its own knowledge_time; as-of selection per query. Generalized: *any* later accession re-reporting a (concept, unit, period) with a different value creates a supersession row (8-K→10-Q, 10-K/A, comparative recasts — e.g., JNJ/Kenvue). Citation precedence: latest authoritative row for the as-of | design §4.2. **One-way door** — changing this later invalidates recorded knowledge_time semantics. Doubles as the automatic restatement detector. |
| U12 | Infra | docker-compose: `postgres:16` + pgvector (facts, chunks, embeddings, FTS); local blob dir (S3-layout); `neo4j:5` added only at Phase 10; Anthropic API (`ANTHROPIC_MODEL`, default `claude-sonnet-5`; `claude-haiku-4-5` for extraction assists) | design §4.1. Store swaps are pivots behind interfaces, not redesigns. |
| U13 | Ex-99.1 headline extractor | Bounded: 3 metrics (revenue, net income, diluted EPS) × ~80 releases; **100% human verification**; rows `source=8K-EX99, preliminary=true` | The only path to preliminary knowledge_time and non-derivable Q4 EPS (design §3.3, §6.2). Growth beyond 5 metrics = DECISIONS.md entry. |

### 0.3 Planning summary — where this market is easy and where it bites

| In your favor | Against you |
|---|---|
| Acquisition fully automated (EDGAR) | Fiscal resolution: per-company FYE, FY-label convention, 52/53-week years |
| Numbers exact from XBRL (U13 headlines the bounded exception) | Concept mapping: tag heterogeneity, JPM, extension tags |
| knowledge_time = exact EDGAR acceptance timestamps | Transcripts: no regulatory source (U5 scope cut) |
| 8-K item codes = native structured event feed | Market data vendor-dependent (U6) |
| NVDA 10:1 split in-corpus = real corporate-actions fixture | Segment queries in v0 scope (U10) |

---

## Part I — Milestone map

| Milestone | Phases | Exit criteria (design §11) |
|---|---|---|
| M0 trustworthy core | 0–5 | quant exact-match ≥ 90%; 100% typed abstention on unanswerables; zero look-ahead violations; every number cited |
| M1 quality & breadth | 6–9 | reranker lift measured; conversation goldens; cache invalidation; migration drill |
| M2 graph (decision-gated) | 10 | graph goldens with edge provenance, or documented no-build |
| M3 agentic research | 11 | multi-hop goldens with reproducible step traces |
| M4 monitoring | 12 | correct, non-duplicate, cited alerts from fixture events |
| M5 hardening subset | 13 | restore drill green; reconciliation drift zero or explained |

---

## Part II — Phases

### Phase 0 — Scaffold, services, CI, protocol

**Objective:** a repo where every later phase has rails.

**Build:** repo layout (0.1); `docker-compose.yml` (`postgres:16` + pgvector); `Makefile` (`up`, `gate PHASE=N`, `gates`, `eval`, `verify-live`); CI running all green gates fixtures-only; `CLAUDE.md` (Part V template); empty `DECISIONS.md` with entry #1: "US market build; sibling Indian project independent"; `.env.example` with `ANTHROPIC_API_KEY`, `TIINGO_API_KEY`, `SEC_EDGAR_USER_AGENT`, `ANTHROPIC_MODEL`. Commit a **snapshot** of SEC `company_tickers.json` as `fixtures/company_tickers.json`; resolve U1 tickers → CIKs against the snapshot → commit `universe.json` (ticker, CIK, FYE-month *hint* only).

**`[HUMAN]`:** create remote repo; Anthropic API key; Tiingo key; **approve U1 universe**; run `make verify-live` once (checks the CIK snapshot against live SEC data; result noted in DECISIONS.md).

**Gate `phase_00.py`:** compose up healthy; env vars present (`SEC_EDGAR_USER_AGENT` contains `@`); `universe.json` resolves against the committed snapshot — no network in CI; CI wiring proven by this gate itself.

---

### Phase 1 — Data spine: schemas, time, units, identity

**Objective:** the bitemporal core and the two resolvers everything else trusts.

**Build:**
- Schemas per design §4: `companies`, `tickers` (point-in-time), `identifiers`, `name_aliases`, `documents`, `facts` (full §4.2 DDL incl. `superseded_by`, `preliminary`, `human_verified`), `fiscal_calendars`, `corporate_actions`, `prices`, `chunks`, `metric_mappings` (empty until Phase 4).
- **As-of read helper** (`AsOfContext`): the only sanctioned way to read `facts`/`chunks`; applies §4.2 as-of semantics.
- **Unit normalizer** (design §4.6): scale words, parenthesized negatives, header-scale inheritance, scale-exempt classes, fail-closed on bare numbers.
- **Fiscal resolver** against `fiscal_calendars` + seed fixtures entered by hand from filings (`[HUMAN]`-verified, ~30 min): NVDA FY2025 all four quarters; MSFT FY2025; AAPL FY2024; WMT FY2025; one 53-week year — **in-window candidate: DE FY2025** (COST's most recent 53-week year, FY2023, sits *outside* the U2 window; verify week count from filing contexts at seed time so Phase 2's absence-branch can't fire spuriously).
- Entity resolution: alias/ticker/name → company_id with ambiguity signaling.

**Unit fixtures (all exact assertions):** `"$1,240 million"`→`1_240_000_000` · `"$1.24 billion"`→`1_240_000_000` · `"(1,234)"` under `"$ in millions"`→`-1_234_000_000` · `"1,234"` under `"in thousands"`→`1_234_000` · `"$6.13"` EPS→`6.13` (scale-exempt) · `"grew 122%"`→percentage never scaled · `"350 bps"`→`0.035` · bare `"1,240"` no context→**reject**. Property test: normalize→render round-trip; invariant: XBRL-sourced values pass through exactly.

**Fiscal resolver matrix (each row a test):**
- `("NVDA","Q3 FY2025")` → period ending late Oct 2024 — **not** calendar Q3 2025
- `("MSFT","Q1 FY2025")` → Jul–Sep 2024
- `("AAPL","FY2024")` → year ending Sep 2024
- `("WMT","FY2025")` vs `("NVDA","FY2025")` → both end Jan 2025, exact dates differ
- `("CAT","Q3 2024")` (Dec-FYE) → calendar Q3, flagged fiscal==calendar
- `("DE","Q3 2024")` (no FY marker, odd FYE) → fiscal Q3 **plus** disambiguation note (design §4.6 policy)
- `("NVDA","revenue in 2024")` (bare calendar year — most common real phrasing) → **year-level** policy: answer states its mapping ("calendar 2024 ≈ NVIDIA FY2025, Feb 2024–Jan 2025")
- `("WMT","2024")` vs `("WMT","FY2024")` → resolutions differ; each states its window
- Period absent from table → **error, never formula fallback** (U8)

**Gate `phase_01.py`:** all fixtures + matrix; grep-lint: no arithmetic quarter-boundary computation anywhere (U8); append-only lint on `facts` (no UPDATE/DELETE in codebase; DB role lacks privileges).

---

### Phase 2 — Ingestion: EDGAR client, facts, narrative, U13, prices

**Objective:** the full U2 corpus loaded, verified, point-in-time-correct.

**Build:**
- **2a. EDGAR client.** Rate limiter (≤10 req/s hard cap, honors `Retry-After`), mandatory User-Agent, accession-keyed idempotent registry. Backfill: per CIK, `submissions.json` → select 10-K/10-Q/8-K in window → fetch primary iXBRL + Ex-99 exhibits → blobs; pull + cache `companyfacts.json`.
- **2b. Facts load.** `companyfacts` → `facts` (concept, unit, period context, accession, acceptance-datetime as knowledge_time). Populate `fiscal_calendars` from period contexts (must match Phase 1 seeds; mismatch = gate failure). Hard rules: **(a) `fy`/`fp` never used for period identity** — periods derive from context start/end dates joined to `fiscal_calendars` (unit test feeds a fact whose fy/fp disagrees with its dates; dates win). **(b) Supersession pass (U11):** any (concept, unit, period) re-reported by a later accession with a different value gets a supersession link — the JNJ/Kenvue recast is expected to surface; hand-confirm, then freeze into the gate.
- **2c. Narrative extraction.** iXBRL HTML → Items 1/1A/7/7A (10-K; parallel 10-Q), Ex-99.1 bodies → heading-aware chunks (design §4.5) → bge-m3 embeddings → pgvector + tsvector indexes.
- **2d. Market data.** Tiingo EOD backfill + actions table (NVDA June 2024 split must appear); Stooq cross-check on 2 tickers.
- **2e. U13 headline extraction.** Per 8-K Item 2.02 release (~80): revenue, net income, diluted EPS (LLM-assisted *extraction* fine; arithmetic not), rows `source=8K-EX99, preliminary=true`, knowledge_time = 8-K acceptance. `[HUMAN]` verifies **every row** (~1.5–2 hr). Without 2e: no preliminary rows, no CI probe 1, no Q4 EPS.

**`[HUMAN]` (~3.5 hr total):** approve universe (if pending); curate IR prepared-remarks manifest (U5, best-effort); **spot-verify 20 facts** (2/company from actual filings) → `fixtures/spot_checks.json`; **verify all U13 rows**.

**Gate `phase_02.py`:**
1. Registry counts per company-window (2×10-K, 6–8×10-Q, ≥8×8-K; exact expectations frozen post-backfill).
2. **All 20 spot-check facts match loaded facts exactly** (value + period + unit) — 100%, any miss is a mapping/context bug.
3. Fiscal calendars: full FY+Q coverage; Phase 1 seeds confirmed; the 53-week audit resolved (DE FY2025 confirmed or absence explicitly asserted post-audit).
4. Narrative: Items 1A + 7 non-empty with correct boundaries on 3 hand-checked filings; every Ex-99.1 yields ≥1 chunk.
5. Prices: no gaps > 3 trading days; NVDA split factor present, correct date; unadjusted × factors ≈ Tiingo adjusted within tolerance.
6. Zero fair-access violations (limiter counters).
7. **U13:** every row `human_verified=true`; each knowledge_time precedes the matching 10-Q/10-K acceptance; `preliminary=true` on all.
8. **fy/fp-independence test** green.
9. **Supersession:** ≥1 comparative-revision supersession detected and hand-confirmed (expected: JNJ/Kenvue); if none, gate passes only with a DECISIONS.md audit entry — never silently.

**Pivots: P-US-1, P-US-2, P-US-3.**

---

### Phase 3 — Eval harness, golden bank, hybrid retrieval, look-ahead gate

**Objective:** the measuring stick exists before anything is tuned; retrieval is point-in-time-safe from birth.

**Build:**
- **Golden bank (60 questions)** → `factual_v0.yaml` (40) + `quant_v0.yaml` (20), committed before retrieval tuning, leakage-linted. Distribution:
  - 12 × direct metric (all 10 companies; JPM expects the caveated mapping)
  - 10 × fiscal traps: NVDA/WMT FY-label collisions, MSFT mid-year FYE, "Q3 2024" ambiguity, one bare-calendar-year ("NVIDIA revenue in 2024"), one 53-week, one cross-company quarter-misalignment, one standalone-Q4 ("NVDA Q4 FY2025 revenue") exercising derivation + preliminary row
  - 8 × point-in-time: ≥3 in the 8-K→10-Q window (U11/U13); 1–2 supersession questions (JNJ/Kenvue guarantees the case; *as-reported-then* and *as-known-now* variants); NVDA split straddles
  - 8 × segment (U10)
  - 6 × cross-company (`comparable=true` legs; 1 deliberately non-comparable expecting degradation)
  - 6 × narrative (risk factors, MD&A)
  - 4 × graph (WMT–COST, CAT–DE, NVDA→hyperscaler concentration) — expected unanswerable until M2; typed refusal until then
  - 6 × unanswerable-by-design: CUSIP (U7), intraday price, analyst target, Q&A-only content (U5 cut), geo sub-segment (U10 cut), out-of-universe company
- **Eval runners:** recall@10, MRR, nDCG@10 (factual); exact-match (quant); behavioral checks (abstained/clarified/flagged-preliminary/stated-interpretation). Baselines recorded in `thresholds.yaml` (ratchet-up only).
- **Hybrid retrieval** (design §6.1): dense (bge-m3/pgvector) + sparse (Postgres FTS) + RRF(k=60) → top-20; **as-of pushdown in both legs**.
- **The look-ahead gate:** CI test asserting no retrieved chunk has `knowledge_time > as_of` across golden historical-as-of samples.

**`[HUMAN]` (~2 hr):** label the 60 questions (gold accessions/sections for factual; gold values+provenance for quant, bound to spot-checks where overlapping).

**Gate `phase_03.py`:** bank schema-valid, committed, leakage lint green; recall@10 ≥ recorded baseline on `factual_v0`; **look-ahead gate green**; RRF beats each single leg on the bank (sanity).

---

### Phase 4 — SQL branch: metric mappings, template compiler, read-only executor

**Objective:** every number the system emits is deterministic, mapped, and provenance-carrying.

**Build:**
- **`metric_mappings`** (design §6.2): ~12 core metrics × default + per-company overrides. JPM: bank-specific pins (`comparable=false`) or NULL mapping with typed abstention; **gross margin for JPM must abstain, not compute**. Tag switches: `valid_from` + series-continuity test.
- **Template compiler + read-only executor:** `metric_value/series/compare`, `segment_value/series`, `derived(TTM|YoY|CAGR|margin)`, `price(...)`; LLM binds parameters only; read-only DB role.
- **Segment facts** (U10): axis/member columns live; NVDA data-center series is the fixture.
- **Q4 derivation** (design §6.2): additive flow metrics only, SQL template, duration-context checks (four contexts exactly tiling FY); derived knowledge_time = 10-K acceptance; instant metrics take FY-end; **EPS never derived** — U13 row or abstention.
- **Verifier v1** (design §6.4): numeric exact-match against inputs; pinned-tag origin check; comparability enforcement; citation precedence (cited accession = latest authoritative for as-of).
- **`execution_v0.yaml`** (25 SQL-path questions → exact result sets) added to the bank.

**`[HUMAN]` (~45 min):** review the mapping table — the curation-with-judgment step.

**Gate `phase_04.py`:** `execution_v0` exact-match 100% (deterministic path — no tolerance); golden direct-metric + segment questions correct under the **gold-answer independence rule** (spot-check-bound golds are the mapping check; programmatic golds only where no overlap); JPM behaviors; tag-switch continuity; **Q4-derivation test:** NVDA Q4 FY2025 revenue = FY − ΣQ1–Q3 exactly, and as-of between the Q4 8-K and the 10-K the U13 preliminary row surfaces, cited `preliminary=true`; no-LLM-arithmetic lint.

**Pivots: P-US-1, P-US-5.**

---

### Phase 5 — Router, generation, verification → **M0 gate**

**Objective:** end-to-end answers with the full answer contract.

**Build:** router (design §6.0) with typed outputs + confidence logging; deterministic entity/fiscal resolution *before* routing; generation over retrieved chunks + SQL results only; verifier wired as a hard post-check (mismatch → one regenerate → abstain); fiscal-disambiguation behaviors (quarter- and year-level) in answers; typed refusals for unanswerable classes; posture guard (§1.4).

**Gate `phase_05.py` = M0 gate:** full golden run — quant exact-match ≥ 90% (answerable); 100% typed abstention on unanswerables; zero look-ahead violations; every number cited `[accession · section · as-of]`; CI probes 1–3 (design §9) green; router misroute rate recorded as baseline; JPM + non-comparable + preliminary-flagging behaviors verified. **Tag `v0.1.0`.**

---

### Phase 6 — API, tracing, cost accounting, supersession-aware cache

**Objective:** a service you can trust and afford, not a script.

**Build:** FastAPI `/query {question, as_of?, conversation_id?}`; JSONL trace per query (router decision, retrieval sets + scores, SQL template + params, verifier verdicts, tokens, cost, latency); daily cost accounting + budget alarm; answer cache keyed (normalized question, as_of, corpus_version), **invalidated by U11 supersession events** — comparative recasts fire this for real, which is a feature: the invalidation path gets exercised.

**Gate `phase_06.py`:** golden run through the API produces complete traces (every eval failure reproducible from trace alone); cache: hit on repeat, **miss after a fixture supersession event**; cost report renders; budget alarm fires on a fixture overrun.

---

### Phase 7 — Sources v2: news + prepared remarks (M1 part A)

**Objective:** the narrative corpus grows beyond filings. (Prices already landed in Phase 2; transcripts scope-cut per U5; analyst reports out of v0 — no free ToS-clean source.)

**Build:** curated RSS ingestion (company IR + market feeds) with dedupe and knowledge_time; prepared-remarks manifest fetcher (U5) — human curates URLs, script fetches/registers/chunks; recency-aware ranking for news in retrieval.

**`[HUMAN]` (~30 min/quarter, ongoing):** maintain the prepared-remarks manifest.

**Gate `phase_07.py`:** fixture RSS batch lands deduped with correct knowledge_time; manifest docs chunked and retrievable; retrieval mixing filings + news respects as-of on both.

---

### Phase 8 — Quality layer: reranker, conversation, conflicts → **M1 gate**

**Objective:** measurably better retrieval; multi-turn usability; honest conflict surfacing.

**Build:** cross-encoder reranker `BAAI/bge-reranker-v2-m3` over fused top-20 → top-8; conversation frame (active company/metric/period/as-of) with deterministic follow-up resolution and the clarification policy (one targeted question, never a guess); conflict handling: preliminary-vs-final and superseded values surfaced in prose ("originally reported X, revised to Y").

**Gate `phase_08.py` = M1 gate:** reranker lifts nDCG@10 on `factual_v0` by a recorded margin (threshold ratchets); 10 multi-turn conversation goldens pass (follow-ups, clarifications, frame switches); conflict-surfacing goldens (JNJ recast, an 8-K/10-Q diff) render both values with correct labels.

---

### Phase 9 — Embedder fine-tune + shadow-index migration drill (M1 complete)

**Objective:** better embeddings *if they earn it*, and proof the index can be rebuilt live.

**Build:** mine training pairs (golden positives + synthetic query-chunk pairs from section headers); contrastive fine-tune of bge-m3 (LoRA); **decision-gated adoption**: adopt only if recall@10 lift ≥ recorded threshold, else document no-go in DECISIONS.md. Either way, run the **shadow-index drill**: build index v2 alongside v1 → A/B on the bank → cutover → rollback → cutover again. **Tag `v0.3.0`.**

**Gate `phase_09.py`:** fine-tune decision recorded with numbers; drill executed — both cutover and rollback verified by golden runs against each index version.

---

### Phase 10 — Graph layer (M2 — decision-gated)

**Objective:** answer exposure/peer questions hybrid+SQL cannot.

**Decision gate first:** run the 4 graph goldens through the M1 system; build only if they fail (expected). A pass = documented no-build, phase closed.

**Build (if triggered):** `neo4j:5` joins compose; edge extraction from Item 1/1A (customer-of, supplier-of, peer-of, exposed-to) with provenance snippets; seeds: WMT–COST, CAT–DE, NVDA→hyperscaler concentration, CAT dealer network; router gains `graph` route; metric legs of graph answers still resolve through Phase 4 templates.

**Gate `phase_10.py`:** 4 graph goldens pass with edge provenance in citations; graph stores no numbers (lint); non-graph goldens unregressed.

---

### Phase 11 — Multi-hop agentic research (M3)

**Objective:** research questions requiring planned tool sequences.

**Build:** planner-executor loop over tools {retrieve, sql, graph, fetch-doc}; budget ≤10 steps + per-query cost ceiling; full citation chain through steps; abstention on budget exhaustion (never a degraded guess); no-LLM-arithmetic preserved (agent may *request* computations, never perform them).

**Gate `phase_11.py`:** multi-hop goldens (added `research_v0.yaml`, ~6 questions) pass with reproducible step traces; budget enforcement fixture (a question engineered to exhaust) abstains correctly; M0–M2 gates unregressed.

---

### Phase 12 — Monitoring agents (M4)

**Objective:** the system tells *you* when something happens.

**Build:** event bus off the daily submissions poll keyed on **8-K item codes** (2.02 results, 5.02 officer changes, 1.01 material agreements, 8.01 other); watchlists; alert templates with citations + as-of stamps; idempotent on accession; news monitors on the Phase 7 feed.

**Gate `phase_12.py`:** synthetic 8-K fixture stream → correct alert, correct item classification, exactly-once per accession; alert text passes the verifier (cited, no invented numbers).

---

### Phase 13 — Hardening (M5 subset)

**Objective:** the failure modes that hit *later* are caught by machinery, not luck.

**Build:** silent-stale detection (expected-filing windows per company; overdue → warning); reconciliation job (facts vs fresh `companyfacts` pull → drift report; drift = supersession candidates or bugs); backup/restore drill (pg_dump + blob dir → clean stack → golden smoke run); runbook: EDGAR fair-access (rate caps, User-Agent, 403 backoff), Tiingo key rotation, disk/cost hygiene, incident notes.

**Gate `phase_13.py`:** restore drill green (golden smoke passes on restored stack); reconciliation zero-drift or every drift explained in DECISIONS.md; stale-detection fixture fires; runbook sections present and current.

---

## Part III — Risks & pivot triggers

| ID | Risk | Signal | Pre-decided pivot |
|---|---|---|---|
| P-US-1 | Concept-mapping ambiguity worse than expected | >20% of (metric, company) cells need research, or spot-check gate fails twice | Shrink v0 metric set to the ~6 unambiguous metrics; rest become explicit "unmapped" abstentions |
| P-US-2 | iXBRL section extraction flaky on some filers | Boundary checks fail on >2 companies | Whole-doc chunking with heading-based soft sections for those filers only |
| P-US-3 | Ex-99.1 HTML too heterogeneous | Chunker garbage on >3 releases | Treat Ex-99.1 as single-chunk docs (they're short); revisit at M1. U13 extraction unaffected — its 100% human gate absorbs heterogeneity |
| P-US-4 | Tiingo free tier insufficient / terms change | Backfill blocked or gaps on >1 ticker | Stooq primary (accept adjusted-only, document the point-in-time caveat); Polygon second fallback |
| P-US-5 | Segment scope balloons | Segment mapping curation >2 hr or gate misses | Cut to NVDA-only segments; restore at M2 |
| P-US-6 | Missing management-narrative depth (U5 bite) | ≥5 golden questions unanswerable without call Q&A | Trigger D-US-1: evaluate one paid transcript API behind an interface; never scrape |
| P-US-7 | 52/53-week logic errors | Any fiscal gate flake involving AAPL/COST/DE/JNJ | Freeze: no formula fallbacks (U8); add the failing year to seed fixtures by hand; root-cause before proceeding |
| P-US-8 | Postgres FTS sparse leg underperforms | Sparse leg drags RRF below dense-only on the bank | Swap in a BM25 engine (e.g., OpenSearch) behind the retrieval interface; thresholds re-baselined via DECISIONS.md |

---

## Part IV — Traceability (phase → design_us.md)

| Phase | Implements |
|---|---|
| 0 | §1.2 universe, §3.1 fair-access env, §4.1 infra |
| 1 | §4.2–§4.6 (bitemporal core, security master, units, fiscal), §9 append-only |
| 2 | §3.1–§3.3, §3.5, §5 (client, facts, narrative, U13, prices, supersession detector) |
| 3 | §6.1, §9 look-ahead gate, §10.1 golden bank |
| 4 | §3.2 + §6.2 (mappings, templates, Q4 derivation), §6.4 verifier |
| 5 | §6.0, §6.4–§6.5, §11 M0 · CI probes 1–3 (§9) |
| 6 | §10.2 observability, §6.6 cache |
| 7 | §3.4, §3.6 |
| 8 | §6.1 rerank, §6.6 conversation, §4.2 conflict surfacing |
| 9 | §4.1 embeddings, D-US-5 |
| 10 | §6.3 |
| 11 | §2.10, §6.4 through agent steps |
| 12 | §7 |
| 13 | §10.2–§10.3, §11 M5 |

---

## Part V — CLAUDE.md template (repo root)

```
# US Equity Financial RAG

Architecture authority: docs/execution_plan_us.md (build order) > docs/design_us.md (design).
This project is self-contained — no external documents are required. The sibling
india_rag/ project is independent; its docs are never an authority here.

Hard rules (violations fail gates):
- U8: fiscal periods resolved from fiscal_calendars, never computed by formula.
- U11: facts are append-only, row-level bitemporal; supersession rows, never edits.
- No-LLM-arithmetic: every number in an answer comes from SQL/deterministic code.
- EDGAR client: never bypass the rate limiter; never remove the User-Agent.
- CI is fixtures-only: no network calls in gates.

Protocol: read this file + the current phase in docs/execution_plan_us.md; implement
to the gate; make gate PHASE=N; all previous gates stay green; deviations go in
DECISIONS.md; [HUMAN] tasks are for the human — stop and ask.
```

---

## Appendix — comparison to the sibling Indian-market plan (informational only)

> `india_rag/` builds the same architecture for Indian equities. **Nothing here is required to build this project.** For the curious: the Indian build's risk lives in *acquisition* (human-in-the-loop downloads; no EDGAR equivalent) and *PDF table extraction* (its Phase 2 gate is ≥90% extraction accuracy, where ours is a 100% mapping spot-check); its fiscal logic is simpler (one national April–March rule vs our per-company calendars); its transcripts are easier (SEBI mandates filing; the US has no equivalent — hence our U5/U13); its market data is easier (official free bhavcopy vs our vendor pin). Same bitemporal core, same no-LLM-arithmetic rule, same gate discipline in both.

---

*End of plan. Design details: `design_us.md`. Anything ambiguous: DECISIONS.md protocol, not improvisation.*
