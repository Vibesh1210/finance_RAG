> **Archived 2026-09-26 (ADR-0019).** The original v0.3 plan, kept unchanged because the code cites its section numbers. Not a description of the current system — see `docs/production/` (HLD §8 lists the differences) and `docs/implementation/roadmap.md`.

# Financial RAG — US Equity Market Design

**Status:** Draft v0.3 · 2026-07-10 (standalone rewrite: all architecture specified in this document; no external doc required to build)
**Companion:** `execution_plan_us.md` (build order, gates, pinned decisions U1–U13)
**Self-containment rule:** This document is the complete design authority for the US build. §13 compares it to the sibling Indian-market project — that section is **informational only** and is never required to build, test, or operate this system.

---

## §0. How to read this document

This is the full design: goals (§1), query requirements (§2), data sources (§3), data model (§4), ingestion (§5), query path (§6), events/monitoring (§7), storage (§8), correctness enforcement (§9), evaluation/observability/compliance (§10), roadmap (§11), open decisions (§12). The execution plan sequences it into 14 gated phases.

**The system in one paragraph:** a decision-support RAG over SEC filings, earnings releases, and market data for a 10-company US equity universe. Numbers live in a bitemporal facts store fed by XBRL (exact, machine-readable); narrative lives in section-aware chunks from iXBRL HTML; a router sends questions to deterministic SQL (metrics), hybrid retrieval (narrative), or both; a verification layer guarantees every number in an answer traces to a stored record as of the question's point in time. The hard problems in this market are *semantic mapping* (which XBRL concept is "revenue" for this company?), *fiscal-calendar resolution* (per-company fiscal years, 52/53-week calendars), and *transcript sourcing* (no regulatory filing requirement) — acquisition and extraction, by contrast, are largely solved by EDGAR + XBRL.

---

## §1. Scope, personas, posture

**§1.1 Personas.** Two users, one person in practice: a **trader** (fast factual lookups, point-in-time honesty, event awareness) and a **researcher** (multi-quarter comparisons, segment trends, narrative reasoning across filings). Interactive latency target: seconds for direct lookups, tens of seconds for multi-hop research; ingestion freshness: daily poll.

**§1.2 Universe (pinned, U1 — 10 US large caps).** Chosen for sector spread, deliberate fiscal-year-end diversity, graph-edge seed pairs, and one issuer whose statements break naive metric assumptions (JPM).

| Ticker | Company | CIK¹ | Sector | FYE² | Why in universe |
|---|---|---|---|---|---|
| AAPL | Apple | 0000320193 | Tech hardware | ~Sep (52/53-wk) | FYE trap: "FY2024" ends Sep 2024; segment-rich |
| MSFT | Microsoft | 0000789019 | Software/cloud | Jun 30 | FYE trap: "Q1 FY2025" = Jul–Sep 2024 |
| NVDA | NVIDIA | 0001045810 | Semiconductors | ~end Jan (52/53-wk) | Hardest FY-label trap (FY2025 ends Jan 2025); 10:1 split June 2024 **inside the corpus window**; segment queries (data center) |
| WMT | Walmart | 0000104169 | Retail | Jan 31 | Second Jan-FYE with *different* convention mechanics; peer pair with COST |
| COST | Costco | 0000909832 | Retail | ~Aug/Sep (52/53-wk) | 53-week fiscal years occur; peer pair with WMT |
| JPM | JPMorgan | 0000019617 | Banking | Dec 31 | Bank statements: no gross margin, revenue is non-trivial to define — stresses metric mapping (§6.2) |
| XOM | ExxonMobil | 0000034088 | Energy | Dec 31 | Commodity sensitivity; different MD&A shape |
| JNJ | Johnson & Johnson | 0000200406 | Healthcare | ~Dec/Jan (52/53-wk) | Pharma segments; **Kenvue separation recast comparatives — in-corpus supersession case (§4.2)** |
| CAT | Caterpillar | 0000018230 | Industrials | Dec 31 | Peer pair with DE; dealer-network disclosures for graph |
| DE | Deere | 0000315189 | Industrials | ~end Oct (52/53-wk) | Fourth odd-FYE; **in-window 53-week candidate (FY2025)**; peer pair with CAT |

¹ CIKs verified at Phase 0 against a committed snapshot of SEC `company_tickers.json` — this table is not ground truth.
² "~" marks 52/53-week calendars where the FYE date moves year to year. **Never hardcode FYE dates**; populate from filings (§4.6).

Graph seeds (§6.3): WMT–COST (peers), CAT–DE (peers), NVDA→hyperscaler customer concentration (disclosed in NVDA 10-K), XOM as macro-sensitivity contrast.

**§1.3 Corpus window (U2).** FY2024 + FY2025 **per each company's own fiscal calendar**, plus all 8-Ks in the same span. Windows deliberately misalign across companies — the misalignment is study material.

**§1.4 Posture (hard rule).** Decision support, **not investment advice**. Every number carries provenance (accession + section + as-of). The system abstains rather than guesses: unanswerable-by-design is a first-class answer type with its own eval questions. No recommendations, price targets, or forward predictions — the system reports what filings and prices *said*, as of *when*.

---

## §2. Requirements & query types

Canonical query classes, each represented in the golden bank (§10.1):

1. **Direct metric:** "What was Apple's operating margin in FY2024?" (resolves to FY ending Sep 2024)
2. **Fiscal trap:** "What was NVIDIA's revenue in Q3 FY2025?" (= quarter ending late **Oct 2024**, not calendar Q3 2025)
3. **Calendar-vs-fiscal ambiguity:** "How did Microsoft do in Q3 2024?" → clarify or apply the pinned resolution policy (§4.6), stating the interpretation in the answer
4. **Segment:** "What was NVIDIA's data-center revenue in FY2025?" — answerable from structured XBRL dimensions (§3.2)
5. **Point-in-time:** "What did we know about Walmart's FY2025 results as of 2024-11-30?" (8-K earnings release vs later 10-Q — §4.2)
6. **Cross-company:** "Compare CAT and DE operating margins, last 4 quarters" (misaligned fiscal quarters surfaced, never silently aligned)
7. **Supersession/restatement:** "What was JNJ's FY2023 revenue as reported then vs as known now?" (comparative recasts, amendments — §4.2)
8. **Narrative:** "What does Deere cite as its main demand risks in the FY2025 10-K?"
9. **Graph:** "Which companies in the universe are exposed to data-center capex?" (§6.3)
10. **Multi-hop research (M3):** "How did WMT's and COST's margin commentary differ as inventory normalized through FY2024?"
11. **Unanswerable-by-design:** CUSIP lookups (excluded identifier, §4.3), intraday prices, sell-side targets, earnings-call Q&A content (scope cut, §3.4), geographic sub-segments (scope cut, D-US-3). The correct behavior is a typed refusal explaining *why*.

---

## §3. Data sources

### §3.1 EDGAR: the filings backbone

The SEC operates a free, bulk, programmatic, ToS-clean distribution system for filings. Interfaces (all keyless, JSON unless noted):

- `data.sec.gov/submissions/CIK##########.json` — per-company filing index (accession numbers, form types, acceptance datetimes, primary documents). Daily diff of this file is the ingestion trigger (§5).
- `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` — every XBRL fact the company ever filed, by concept, with units and period contexts. The primary structured-numbers source (§3.2).
- `data.sec.gov/api/xbrl/companyconcept/...` — one concept's history for one company.
- `data.sec.gov/api/xbrl/frames/...` — one concept across all filers for one period (cross-company checks).
- `efts.sec.gov/LATEST/search-index?q=...` — full-text search (convenience, not a pipeline dependency; smoke-test the parameter shape at first use).
- Bulk archives `companyfacts.zip` / `submissions.zip` (nightly) — the scale path; per-company APIs suffice for 10 names.

**Fair-access rules (hard, encoded in the client):** ≤10 requests/second; a declared `User-Agent` containing a contact email; prefer bulk files for large pulls; back off on 403/`Retry-After`. Violations get IP-throttled.

**Forms in scope:**

| Form | Role | Notes |
|---|---|---|
| 10-K | Annual report | iXBRL since 2019 → clean HTML + tagged numbers |
| 10-Q | Quarterly report | Same |
| 8-K | Material events | Item 2.02 + Exhibit 99.1 = **earnings press release**, lands 2–4 weeks *before* the 10-Q — the point-in-time workhorse (§4.2) |
| 10-K/A, 10-Q/A | Amendments | First-class bitemporal cases (§4.2) |
| DEF 14A | Proxy | Stretch — decision D-US-4 (§12) |

Out of scope: S-1, 20-F, 424B, Forms 3/4/5.

### §3.2 XBRL structured facts — the risk is mapping, not extraction

Numbers arrive machine-readable and exact (value + unit + period context + accession) via `companyfacts`. The residual risk is **concept mapping**:

- **Tag heterogeneity.** "Revenue" may be `us-gaap:Revenues`, `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`, an industry variant — and a company may switch tags between years. Naive tag-keyed queries silently return nulls or mix series.
- **Banks are the stress case.** JPM has no `Revenues` in the retail sense. If the metric layer handles JPM honestly (pinned bank-specific mapping + caveat, or explicit abstention), it is designed correctly. Gross margin for JPM must abstain, not compute.
- **Extension tags.** Custom `aapl:`/`nvda:` concepts (commonly 10–20% of a filing's tags) are *not cross-company comparable*. Policy: usable for single-company questions when pinned in `metric_mappings`; never for cross-company comparisons (verifier-enforced, §6.4).
- **Dimensions.** Segment facts carry XBRL axes/members (business-segment axis → "Data Center"), making query class 4 structured rather than extractive. v0 scope: business-segment axis only (D-US-3).
- **`fy`/`fp` are not period identity.** Those `companyfacts` fields describe the *filing's* fiscal focus, not the fact's period. Period identity derives exclusively from context start/end dates joined against `fiscal_calendars` (§4.6). Using `fy`/`fp` for period assignment is a gate-enforced defect.

**Mitigation — `metric_mappings` (§6.2):** per (metric, company), a hand-verified pinned tag with provenance and `verified_by`. 10 companies × ~12 core metrics = an afternoon of curation. Cross-company queries may only traverse mappings marked `comparable`.

**What XBRL does not cover — two load-bearing gaps:**

1. **Exhibit 99 carries no XBRL tagging requirement.** Earnings-release numbers exist only as press-release HTML; `companyfacts` is built from tagged 10-K/10-Q facts. Without a dedicated path, the §4.2 preliminary fact row — the point-in-time workhorse — would never exist. Resolution: the bounded, human-gated Ex-99.1 headline extractor (§3.3, pin U13).
2. **Standalone Q4 facts are generally absent.** Q4 is reported in the earnings release; the 10-K files only FY figures. "NVDA Q4 FY2025 revenue" has no direct fact. Resolution: deterministic Q4 derivation in the metrics layer (§6.2) plus the U13 preliminary row where extracted.

### §3.3 Narrative text: iXBRL HTML

10-K/10-Q primary documents are inline-XBRL HTML — no OCR, no PDF-table gauntlet:

- Section extraction targets Item 1 (Business), 1A (Risk Factors), 7 (MD&A), 7A, and Item 8 notes, via HTML structure + heading heuristics; section boundaries are gate-asserted on hand-checked filings.
- **8-K Exhibit 99.1 earnings releases** precede each 10-Q and are less-standardized HTML — the one place extraction needs tolerance. Because Ex-99 is **untagged** (§3.2), a **bounded headline extractor** (U13) pulls revenue, net income, and diluted EPS per release — ~80 releases, every row human-verified, stored `source=8K-EX99, preliminary=true`. Statement-scale extraction stays out of scope; this narrow exception is what makes §4.2's point-in-time behavior implementable.
- A vision-parse fallback is *defined but dormant* — only relevant if some filer's HTML proves pathological.

### §3.4 Transcripts — the honest gap

There is **no US regulatory requirement to file earnings-call transcripts**. Vendor and media transcripts (LSEG, S&P, Motley Fool, Seeking Alpha) are ToS-restricted; scraping them is rejected on posture grounds (§10.3). **Pinned (U5/D-US-1):** v0 uses 8-K earnings releases + voluntarily IR-posted prepared remarks/CFO commentary (e.g., NVIDIA's written CFO commentary), fetched via a small human-curated manifest. Full transcript coverage is a deferred decision with an explicit trigger (§12).

### §3.5 Market data — vendor-pinned

No free official EOD file exists for US equities; access is via vendors:

| Source | Free tier | Assessment |
|---|---|---|
| Tiingo | Generous EOD history, adjusted+unadjusted, split/dividend factors | **Pinned primary** (U6) |
| Stooq | Keyless CSV EOD | **Pinned fallback** — adjusted-only (limitation documented) |
| Alpha Vantage / Polygon | ~25 req/day / 5 req-min + 2y | Rejected: too tight / too shallow |
| yfinance | Unofficial | **Rejected**: breaks without notice |

Storage principle: **unadjusted prices + a corporate-actions table** (factors from Tiingo), adjusted at query time. Never store only pre-adjusted series — that back-propagates today's knowledge into history and breaks point-in-time (§4.2). **Price-answer basis (pinned):** split-adjusted only; dividends stored but total-return series out of v0; answers state their basis explicitly.

### §3.6 News / sentiment

M4 scope (§7): curated RSS (company IR feeds + market news) plus the 8-K item-code stream, which serves as a *structured* material-events feed. Not built before M4.

---

## §4. Data model

### §4.1 Store map (pinned infra, U12)

One database, few moving parts, every store versioned in docker-compose:

- **PostgreSQL 16 + pgvector** — system of record: registry, facts, fiscal calendars, security master, prices, chunks *and* their embeddings (pgvector HNSW index), plus Postgres full-text search for the sparse leg of hybrid retrieval (§6.1). Swapping sparse to OpenSearch, or dense to a dedicated vector DB, is a contained change behind the retrieval interface — a pivot, not a redesign.
- **Blob store** — raw fetched artifacts (iXBRL HTML, Ex-99 exhibits, `companyfacts.json` snapshots) on local disk keyed by accession number, S3-compatible layout so a bucket swap is config-only. Raw blobs are immutable; reprocessing is always possible.
- **Neo4j** — added **only at M2** (Phase 10, decision-gated) for the graph layer. Absent until then.
- **LLM** — Anthropic API; generation model pinned via `ANTHROPIC_MODEL` env (default `claude-sonnet-5`); a cheaper tier (`claude-haiku-4-5`) is permitted for bulk extraction assists (U13, section classification). Model changes are DECISIONS.md entries.
- **Embeddings** — `BAAI/bge-m3` (U9), local inference; swap seam to `bge-base-en-v1.5` under latency/VRAM pressure (D-US-5).

### §4.2 Bitemporal facts store (the core invariant)

Every numeric fact is a **row-level bitemporal, append-only** record:

```sql
facts(
  fact_id        BIGSERIAL PRIMARY KEY,
  company_id     INT  REFERENCES companies,
  concept        TEXT,            -- us-gaap tag or 8K-EX99 pseudo-concept
  axis TEXT NULL, member TEXT NULL,  -- segment dimensions (D-US-3)
  value          NUMERIC,
  unit           TEXT,            -- 'USD', 'USD/share', 'shares'
  period_start   DATE, period_end DATE,   -- valid time (the period the number describes)
  period_kind    TEXT,            -- 'duration' | 'instant'
  knowledge_time TIMESTAMPTZ,     -- EDGAR acceptance datetime of the reporting accession
  accession      TEXT,            -- provenance
  source         TEXT,            -- '10-K' | '10-Q' | '8K-EX99' | 'derived'
  preliminary    BOOLEAN DEFAULT FALSE,
  superseded_by  BIGINT NULL REFERENCES facts(fact_id),
  human_verified BOOLEAN DEFAULT FALSE    -- U13 rows and spot-checks
)
```

**As-of semantics.** A query with `as_of = T` sees exactly the rows with `knowledge_time <= T`, and among duplicates for the same (company, concept, unit, period), the one not superseded by any row whose `knowledge_time <= T`. No updates, no deletes — corrections are new rows.

**Three market-specific wrinkles, all handled by the same machinery:**

1. **The 8-K → 10-Q duplicate-fact problem.** Quarterly revenue appears twice: in the earnings release (knowledge_time = 8-K acceptance) and in the 10-Q weeks later. The 8-K row exists **only via the U13 extractor** (§3.3) — XBRL alone never creates it. Each row keeps its own knowledge_time; as-of selection surfaces whichever was known at the query instant. On a value difference the 10-Q row supersedes the preliminary row (the diff is itself a signal). Queries dated between the two acceptances must return the 8-K value — the canonical CI probe (§9).
2. **Supersession is general — amendments are just the loudest case.** The same (concept, unit, period) recurs across accessions: original filing plus comparatives re-reported in later filings, sometimes with changed values. Any later accession re-reporting an existing (concept, unit, period) with a **different value** creates a supersession row — the automatic restatement/revision detector; 10-K/A is one trigger among many. Real in-corpus case: **JNJ's Kenvue separation recast prior-period comparatives as discontinued operations.** "FY2023 revenue as reported then vs as known now" must return different numbers.
3. **knowledge_time is the EDGAR acceptance datetime**, never the filing date — acceptance timestamps are exact and authoritative.

**Citation precedence.** Answers cite the latest authoritative row for their as-of date; superseded/preliminary rows are cited only by as-of queries predating the supersession, and current answers may note "originally reported as X" (verifier-checked, §6.4).

### §4.3 Security master & identifiers

```sql
companies(company_id, cik UNIQUE, name, sector, fye_month_hint)
tickers(company_id, ticker, exchange, valid_from DATE, valid_to DATE NULL)  -- point-in-time aliases
identifiers(company_id, scheme TEXT, value TEXT)   -- scheme ∈ {'FIGI'}
name_aliases(company_id, alias TEXT)               -- "Apple", "Apple Inc.", "AAPL"
```

- **CIK** is the primary join key (SEC-native, stable, free). **Ticker** resolution is point-in-time (tickers change; the alias table carries validity windows). **FIGI** (OpenFIGI, free) is the cross-domain instrument identifier.
- **CUSIP/ISIN are deliberately excluded** — CUSIPs are licensed (CUSIP Global Services) and US ISINs embed the CUSIP. A golden unanswerable question (§2.11) locks the exclusion in behaviorally.
- Entity resolution at query time: alias/ticker/name → company_id, with ambiguity surfaced to the clarification policy (§6.6).

### §4.4 Document registry

Every fetched artifact is registered before processing: `documents(accession PRIMARY KEY, company_id, form, filed_date, acceptance_datetime, primary_doc_url, blob_path, status)`. The accession number is the native globally-unique idempotency key for the whole pipeline.

### §4.5 Chunks

Narrative text is chunked **heading-aware, never crossing section boundaries**; target ≤ ~800 tokens with ~100-token overlap inside long sections. Metadata per chunk:

```
chunks(chunk_id, accession, company_id, doc_type, section,   -- 'Item 1A', 'Item 7', 'EX-99.1', ...
       fiscal_context TEXT NULL,     -- e.g. 'FY2025 Q2' when the doc implies it
       knowledge_time TIMESTAMPTZ,   -- inherited from the accession
       text, tsv tsvector, embedding vector)
```

`knowledge_time` on chunks is what makes point-in-time retrieval enforceable (§6.1, §9). Ex-99.1 releases that resist section extraction may be stored as single chunks (pivot P-US-3) — they are short.

### §4.6 Units & fiscal calendars

**Units.** XBRL facts arrive exact with unit attributes, so the normalizer is mostly a **validator**; its parsing role covers narrative text and LLM I/O guardrails. It owns: scale words (thousand/K, million/mm/M, billion/bn/B), parenthesized negatives ("(1,234)" = −1,234), table-header scale inheritance ("$ in millions" applies statement-wide), scale-exempt classes (EPS, dividends/share, ratios, percentages, bps). Bare numbers with no scale context are **rejected, never guessed** (fail-closed). Invariant: normalizer output for any XBRL-sourced fact equals the raw XBRL value exactly.

**Fiscal calendars (the most bug-prone area of this build — pin U8).** Three interacting traps: FYE varies per company (five distinct months across ten names); the **FY-label convention** — a fiscal year is labeled by the calendar year containing its end (NVIDIA "FY2025" ≈ Feb 2024–Jan 2025; Walmart "FY2025" = Feb 2024–Jan 2025; Apple "FY2024" ends Sep 2024); and **52/53-week calendars** (AAPL, COST, JNJ, DE) where FYE dates move annually and some years contain a 14-week Q4.

**Design rule (hard):** fiscal periods are **never computed, always resolved** from:

```sql
fiscal_calendars(company_id, fiscal_year INT, fiscal_period TEXT,  -- 'FY'|'Q1'..'Q4'
                 period_start DATE, period_end DATE,
                 weeks INT,                    -- 13|14|52|53
                 source_accession TEXT, knowledge_time TIMESTAMPTZ)
```

populated from XBRL period contexts (seeded by `fiscalYearEnd` in submissions JSON, ground-truthed by per-report contexts). Formula-computed quarter boundaries are a lint-enforced defect.

**Ambiguity policy.** Quarter-level ("Q3 2024", no FY marker): resolve to the company's fiscal Q3 when the company is unambiguous, and say so in the answer; clarify interactively when companies with different calendars are in scope. Year-level ("NVIDIA revenue in 2024" — the most common real-user phrasing): calendar 2024 spans the tail of FY2024 and most of FY2025; the answer states its mapping explicitly ("calendar 2024 ≈ NVIDIA FY2025, Feb 2024–Jan 2025").

### §4.7 Corporate actions

In scope: **splits** and **dividends** (Tiingo factors + 8-K confirmation), buyback *disclosures* (share counts from filings — affect per-share metrics, not prices). No bonus/rights issues in this market's practice; spin-offs out of scope (JNJ/Kenvue enters as a *reporting* recast, §4.2, not a price event we model).

**Pinned in-corpus fixture: NVDA 10:1 split, effective June 2024** — every price/per-share query spanning it exercises adjustment logic on real data. Adjustments computed at query time from the actions table (§3.5); split-adjusted basis only (U6).

---

## §5. Ingestion pipeline

1. **Poll** (daily): diff `submissions.json` per CIK → new accessions → fetch queue. Idempotent by accession.
2. **Fetch**: primary iXBRL doc + Ex-99 exhibits for 8-Ks → blob store; register in `documents`.
3. **Facts load**: refresh `companyfacts` per company → upsert facts with full provenance; populate `fiscal_calendars` from period contexts; run the **supersession pass** (§4.2: later accession + different value → supersession link).
4. **Narrative extraction**: iXBRL HTML → sections → chunks (§4.5) → embed (bge-m3) → index (pgvector + tsvector).
5. **U13 headline extraction**: per 8-K Item 2.02 release — revenue, net income, diluted EPS → preliminary rows; 100% human verification before the rows are queryable.
6. **Market data**: Tiingo EOD backfill + daily append; actions table maintained alongside.
7. **Rate limiting** (§3.1) wraps all EDGAR traffic; the limiter is not configurable above the fair-access cap.

`[HUMAN]` in ingestion is small and bounded: approve universe, curate the prepared-remarks manifest (§3.4), spot-verify 20 facts, verify U13 rows (~3.5 hr total, one-time).

---

## §6. Query path

### §6.0 Router

An LLM classifier with a typed output maps each question to one of: `metric` (SQL path), `narrative` (retrieval path), `hybrid` (both, merged at generation), `graph` (M2+), `research` (M3 agentic), `unanswerable` (typed refusal with reason), `clarify` (ambiguity per §4.6/§6.6). Routing decisions are logged with confidence; misroutes are eval failures, not silent degradations. Before routing: entity resolution (§4.3) and fiscal resolution (§4.6) run deterministically — the router never guesses periods.

### §6.1 Hybrid retrieval (narrative path)

- **Dense leg:** bge-m3 embeddings, pgvector HNSW, cosine, top-50.
- **Sparse leg:** Postgres FTS (`ts_rank_cd`) over chunk text, top-50. (BM25-class engine behind the same interface is an approved pivot if FTS quality disappoints.)
- **Fusion:** Reciprocal Rank Fusion (k=60) → top-20.
- **Rerank (from M1/Phase 8):** cross-encoder `BAAI/bge-reranker-v2-m3` over fused top-20 → top-8 to generation.
- **As-of filter is a hard pushdown**, not post-filtering: `WHERE knowledge_time <= :as_of` in both legs. No chunk newer than the question's as-of can *ever* reach the LLM — enforced by the look-ahead gate in CI (§9).
- Filters: company, doc_type, section, fiscal_context when the router extracts them.

### §6.2 Metrics store & SQL path

**No free-form text-to-SQL against the database.** The LLM selects a **template** and binds parameters; templates are reviewed SQL executed by a read-only role:

- `metric_value(company, metric, period)` · `metric_series(company, metric, last_n)` · `metric_compare(companies[], metric, period)` · `segment_value/series(company, segment_metric, ...)` · `derived(TTM | YoY | CAGR | margin_ratio, ...)` · `price(company, date | range)` — each resolves metrics through:

```sql
metric_mappings(metric_key, company_id NULL,        -- NULL = default; company rows override
                us_gaap_tag, unit, comparable BOOL,
                provenance, verified_by, valid_from)
```

- JPM's revenue/margin metrics get bank-specific pins (`comparable=false`, answers carry a caveat) or explicit NULL mappings with typed abstention.
- Tag switches across years: mappings carry `valid_from`; series must be continuous across the switch (tested).
- **No-LLM-arithmetic (hard rule):** every computed number (TTM, CAGR, margins, deltas, Q4 derivation) is produced by SQL/deterministic code. The LLM narrates results; it never adds, divides, or rounds into an answer.
- **Q4 derivation (pinned).** Standalone Q4 facts are absent from XBRL (§3.2). Additive flow metrics (revenue, net income, CFO, capex): Q4 = FY − Q1 − Q2 − Q3, computed as a SQL template with duration-context checks (same concept + unit, four contexts exactly tiling the fiscal year); derived rows carry `source='derived'`, knowledge_time = 10-K acceptance. Instant (balance-sheet) metrics: Q4-end value *is* the FY-end value. **Non-additive metrics are never derived by subtraction** — quarterly diluted EPS does not sum to annual EPS (share-count averaging), so Q4 EPS surfaces from the U13 preliminary row or abstains. Where a U13 row exists, it surfaces at its earlier knowledge_time.

### §6.3 Graph layer (M2, decision-gated)

Built only if golden graph questions prove unanswerable by hybrid+SQL alone. Neo4j; nodes = companies/segments/named counterparties; edges = peer-of, customer-of, supplier-of, exposed-to, each with provenance (accession + section snippet). Seed edges from §1.2; extraction from Item 1/1A. Graph queries answer exposure/peer questions with edge provenance in citations; the graph never stores numbers — metric legs of a graph answer still resolve through §6.2.

### §6.4 Generation & verification

Generation receives only: retrieved chunks (with citations), SQL results (with row provenance), and the conversation frame. The answer contract:

- Every numeric token in the answer must **exactly match** a provided record (string-normalized comparison; the verifier extracts numbers from the draft and matches against inputs — a mismatch is a hard failure → regenerate once → abstain).
- Every number carries a citation `[accession · section/table · as-of]`.
- **Pinned-tag origin check:** SQL-sourced numbers must originate from the pinned mapping for that (metric, company); a mapping bypass is a hard failure.
- **Comparability check:** cross-company answers assert `comparable=true` on every leg, else degrade to per-company statements with an explicit non-comparability note.
- **Citation precedence** (§4.2): cited accession must be the latest authoritative for the query's as-of.
- **Preliminary flagging:** U13-sourced numbers are labeled preliminary in the prose.
- Posture guard (§1.4): advice-like outputs blocked by template.

### §6.5 Point-in-time query semantics

`as_of` is an explicit query parameter (default: now). It flows as one value through router → retrieval pushdown → SQL templates → verification. Answers state their as-of when it isn't "now". The three CI probes in §9 hold this end to end.

### §6.6 Conversation

Server-side conversation frame: active company/companies, metric, period, as-of. Follow-ups resolve against the frame deterministically before routing ("and for Costco?" → same metric/period, company swapped). The **clarification policy** fires when entity or period resolution is ambiguous (§4.6) — one targeted question, never a guess. Answer cache keyed on (normalized question, as_of, corpus_version), invalidated by supersession events (§4.2) — a restatement flushes affected entries.

---

## §7. News, events, monitoring (M4)

- **8-K item codes are the native structured event feed**: 2.02 (results), 5.02 (officer changes), 1.01 (material agreements), 8.01 (other). Monitors key on item codes from the daily submissions poll — no scraping.
- News: curated RSS (IR feeds + market sources), deduped, stored with knowledge_time; retrievable with recency-aware ranking.
- Watchlist alerts render from templates with citations and as-of stamps; idempotent on accession (no duplicate alerts).
- None of this is built before M4.

---

## §8. Storage & scale

10 companies × 2 fiscal years ≈ 2×10-K + 6–8×10-Q + ~8 8-K per company, plus prices: comfortably < 5 GB including embeddings. `companyfacts` JSON cached raw (~1–5 MB/company) for reproducibility. Everything runs in docker-compose on a laptop; the S3-compatible blob layout and the retrieval interface seams are the scale path, exercised only if the universe grows.

---

## §9. Point-in-time enforcement (CI)

Correctness here is *tested*, not asserted:

- **The look-ahead gate (every CI run):** for a sample of golden questions with historical as-of dates, assert that no retrieved chunk and no SQL row has `knowledge_time > as_of`. Any hit fails the build.
- **Probe 1 — 8-K-before-10-Q:** a query dated between an earnings release and its 10-Q returns the 8-K figure with 8-K provenance (the U13 row; without U13 this probe is unimplementable).
- **Probe 2 — Supersession:** as-of queries straddling a superseding accession's acceptance return original vs revised respectively — the JNJ/Kenvue recast is the guaranteed in-corpus case; a 10-K/A, if present, is a second.
- **Probe 3 — Split window:** NVDA per-share/price queries as-of before, between, and after the June 2024 split events adjust correctly and cite the action.
- **Append-only audit:** CI asserts no UPDATE/DELETE statements against `facts` exist in the codebase (lint) and the DB role lacks the privileges (defense in depth).

---

## §10. Evaluation, observability, compliance

### §10.1 Evaluation methodology

- **Golden bank: 60 questions**, committed at Phase 3 *before retrieval tuning*, never used as training data (leakage lint enforces). Files: `evals/golden/factual_v0.yaml` (40 narrative/retrieval questions → gold accession+section), `evals/golden/quant_v0.yaml` (20 numeric → gold value+provenance tuples); Phase 4 adds `execution_v0.yaml` (25 SQL-path questions → exact result sets). Distribution spans all §2 classes, weighted toward this market's risks (fiscal traps, segments, supersessions, point-in-time) — exact cut in the execution plan.
- **Gold-answer independence rule:** where a golden question overlaps one of the 20 human spot-checks, the gold binds to the *human-verified* value. Golds derived programmatically from `companyfacts` pass through the same mapping under test and can only catch plumbing bugs — they're reserved for questions with no overlapping spot-check.
- **Runners & metrics:** retrieval — recall@10, MRR, nDCG@10 vs `thresholds.yaml` baselines (ratchet: thresholds only move up); quant — exact match; behavioral — typed checks (abstained? clarified? flagged preliminary? stated fiscal interpretation?).
- **`[HUMAN]` labels the bank (~2 hr)** — the quality anchor for everything downstream.

### §10.2 Observability & cost

Every query writes a JSONL trace: router decision + confidence, retrieval sets with scores, SQL template + bound params, verifier verdicts, token counts, model, latency, cost. Per-day cost accounting with a budget alarm. Traces are the debugging surface for eval failures — an eval failure must be reproducible from its trace alone.

### §10.3 Compliance posture

- §1.4 verbatim: personal research/decision-support, not investment advice.
- EDGAR fair-access compliance is hard-coded (§3.1) and in the runbook.
- No redistribution of vendor data (Tiingo terms); no scraping ToS-restricted transcript sources (§3.4); CUSIP/ISIN exclusion (§4.3) is itself a compliance decision.

---

## §11. Roadmap & milestone exit criteria

- **M0 — Trustworthy core (end of Phase 5).** Facts + narrative for the full universe; router + SQL + hybrid retrieval + verification live. *Exit:* quant golden exact-match ≥ 90% on answerable questions; 100% typed-abstention on unanswerable set; zero look-ahead violations; every number cited to an accession; JPM behaviors correct.
- **M1 — Quality & breadth (Phases 6–9).** API + tracing + cache; news/prepared-remarks sources; reranker + conversation + conflict handling; embedder fine-tune with shadow-index migration drill. *Exit:* reranker lifts nDCG@10 by a measured margin; 10 multi-turn conversation goldens pass; cache invalidation-on-supersession tested; migration drill (build v2 index → A/B → cutover → rollback) executed.
- **M2 — Graph (Phase 10, decision-gated).** *Exit:* graph goldens pass with edge provenance — or a documented no-build decision.
- **M3 — Agentic research (Phase 11).** Planner-executor with tool budget (≤10 steps, cost ceiling), full citation chains. *Exit:* multi-hop goldens pass with reproducible step traces; no-LLM-arithmetic preserved through agent steps.
- **M4 — Monitoring (Phase 12).** 8-K item-code monitors, watchlists, alerts. *Exit:* synthetic-event fixture produces correct, non-duplicate, cited alerts.
- **M5 — Hardening subset (Phase 13).** Silent-stale detection, facts-vs-source reconciliation, backup/restore drill, runbook. *Exit:* restore drill green; reconciliation drift zero or explained.

---

## §12. Open decisions

| ID | Decision | Pinned default | Revisit trigger |
|---|---|---|---|
| D-US-1 | Transcript sourcing | v0 = 8-K releases + IR prepared remarks; no vendor transcripts | ≥5 golden questions unanswerable without Q&A content |
| D-US-2 | Market-data vendor | Tiingo primary, Stooq fallback | Backfill gaps/errors on >1 ticker, or free-tier terms change |
| D-US-3 | Segment depth | Business-segment axis only; no geo | Golden segment questions need geo AND mapping curation stays < 2 hr |
| D-US-4 | DEF 14A (proxy) | Out of v0 | Comp/governance questions appear in real usage |
| D-US-5 | Embedding model | `bge-m3` | Latency/VRAM pressure → `bge-base-en-v1.5` |

All changes go through the DECISIONS.md protocol (execution plan, Part 0).

---

## §13. Appendix — comparison to the sibling Indian-market project (informational only)

> This project shares its architectural DNA with a sibling Indian-market build (`india_rag/`). **Nothing below is required to build, test, or operate this system.** It exists because the two projects illuminate each other's design choices.

| Dimension | India | US (this project) |
|---|---|---|
| Filing distribution | Exchange sites, anti-bot, human-in-the-loop downloads | EDGAR: free, bulk, programmatic |
| Filing format | PDF — table extraction is the top risk | iXBRL HTML + XBRL facts — **mapping** is the top risk |
| Transcripts | Filed with exchanges (SEBI LODR) — easy | No filing requirement — scope-cut to releases + prepared remarks |
| Market data | Official free bhavcopy | Vendor-pinned (Tiingo/Stooq) |
| Fiscal calendar | One national rule (April–March) | Per-company FYE + FY-label convention + 52/53-wk — harder |
| Units | crore/lakh, ₹ | thousand/million/billion, $, parenthesized negatives — easier |
| Identifiers | ISIN-first | CIK + ticker + FIGI; no CUSIP/ISIN (licensing) |
| Event feed | Scraped announcements | 8-K item codes — structured, native |
| knowledge_time provenance | Publication dates (fuzzy) | EDGAR acceptance timestamps (exact) |
| Preliminary numbers | Results filed once | 8-K precedes 10-Q → U13 extractor + preliminary rows |

---

*End of design. Build order, gates, fixtures, and pinned decisions U1–U13: `execution_plan_us.md`.*
