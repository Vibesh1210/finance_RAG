# 02 · High-level design

## 1. The system on one page

Two pipelines share one database. The **offline pipeline** (ingestion) runs once, or when
new filings appear, and fills the stores. The **online pipeline** (answering) runs per
question and only reads.

```
 OFFLINE — ingestion (src/us_rag/ingest/)                     ONLINE — answering (src/us_rag/query/)
 ─────────────────────────────────────────                    ──────────────────────────────────────

  SEC EDGAR ──(rate-limited client)──┐                          question + as_of date
                                     │                                   │
          ┌──────────────────────────┼───────────────┐                   ▼
          ▼                          ▼               ▼            ┌─────────────┐
   companyfacts.json          10-K/10-Q HTML    8-K Ex-99.1       │   ROUTER    │ rules, no model
   (tagged numbers)           (filing text)     (press release)   │ company +   │
          │                          │               │            │ period first│
          ▼                          ▼               ▼            └──────┬──────┘
    facts load               sections → chunks   headline extract        │
    + fiscal calendars        → embeddings       (LLM reads, human       │
    + restatement links                           verifies) [pending]    │
          │                          │               │         ┌─────────┼──────────┬──────────┐
          ▼                          ▼               ▼         ▼         ▼          ▼          ▼
   ┌─────────────────────────────────────────────────────┐  metric   narrative   refuse    clarify
   │  PostgreSQL 16 + pgvector (one database)            │     │         │
   │   facts · fiscal_calendars · metric_mappings        │◄────┘         │  read-only role
   │   documents · companies/tickers/aliases             │               │  as_of filter in
   │   chunks (text + tsvector + 1024-d vector)          │◄──────────────┘  every query
   └─────────────────────────────────────────────────────┘
                                                            metric  → exact value + citation → verifier
   blobs/ (raw downloaded files, by accession, gitignored)  narrative → top passages → [Gemini, opt-in]
                                                            → Answer(status, text, citations)
```

## 2. The three ideas everything hangs on

1. **Two lanes.** Numbers are *looked up* (SQL over tagged XBRL facts). Words are
   *searched* (hybrid search over chunks). A number never comes from text search or from
   a model.
2. **Two clocks.** Every fact and every chunk carries the period it describes *and* the
   moment it became public (`knowledge_time` = SEC acceptance timestamp). Every read is
   filtered to `knowledge_time <= as_of`.
3. **One "no".** Anything the system can't answer exactly — unknown period, missing
   mapping, ambiguous company, out-of-scope data — becomes a typed refusal or a
   clarifying question, never a guess.

## 3. Components

| Component | Code | Responsibility | LLD |
|---|---|---|---|
| Security master | `entities.py`, `universe.py`, `store/seed.py` | Company / ticker / alias → one company, or "ambiguous" | [data_model](lld/data_model.md) |
| Fiscal resolver | `fiscal.py` | "Q3 FY2025", "FY2024", "2024" → exact dates from `fiscal_calendars` | [data_model](lld/data_model.md) |
| Units normaliser | `units.py` | Text quantities → exact Decimals; refuses when scale is unknown | [ingestion](lld/ingestion.md) |
| Bitemporal store | `store/asof.py`, `db/migrations/` | The as-of read rule; append-only writes | [data_model](lld/data_model.md) |
| EDGAR client + backfill | `ingest/edgar.py`, `ingest/backfill.py` | Polite download of filings into `blobs/` + `documents` | [ingestion](lld/ingestion.md) |
| Facts loader | `ingest/facts_load.py` | XBRL → `facts`, `fiscal_calendars`, restatement links | [ingestion](lld/ingestion.md) |
| Narrative pipeline | `ingest/narrative.py` | HTML → sections → chunks → embeddings | [ingestion](lld/ingestion.md) |
| Headline extractor (U13) | `ingest/headline.py` | Press-release revenue / net income / EPS, human-gated | [ingestion](lld/ingestion.md) |
| Prices | `ingest/prices.py` | Tiingo daily prices + split/dividend table (not yet run) | [ingestion](lld/ingestion.md) |
| Numbers engine | `query/metrics.py` | Metric registry, exact lookup, compare, series, derived values, Q4 | [numbers_engine](lld/numbers_engine.md) |
| Retriever | `query/retrieve.py` | Dense + keyword search, RRF fusion, as-of pushdown | [retrieval](lld/retrieval.md) |
| Router | `query/router.py` | Question → typed route + confidence + reason | [answering](lld/answering.md) |
| Answer pipeline | `query/generate.py` | `answer()`: route → fetch → write → verify | [answering](lld/answering.md) |
| Verifier | `query/verify.py` | Number/citation/comparability checks | [answering](lld/answering.md) |
| Evaluation | `eval/`, `golden/`, `gates/` | Test questions, retrieval metrics, look-ahead scan, phase gates | [03](03_evaluation_and_testing.md) |

## 4. Key flows

### 4.1 A number question

```
"What was Apple's total net sales for fiscal year 2025?"   as_of = 2026-03-01
  │
  ├─ router.scan_entities ........ "Apple" → AAPL
  ├─ router.classify ............. metric words + company + period → route = metric
  ├─ generate.extract_metric_key . "net sales" → revenue
  ├─ generate.extract_period ..... "fiscal year 2025" → FY2025
  ├─ metrics.metric_value
  │     ├─ fiscal.resolve ........ AAPL FY2025 → 2024-09-29 … 2025-09-27 (table lookup)
  │     ├─ resolve_mapping ....... revenue + AAPL → RevenueFromContractWithCustomer…  (override beats default)
  │     └─ AsOfContext.facts ..... rows known by as_of, not yet superseded → latest one
  ├─ verify ...................... value / citation / comparability checks
  └─ Answer: "AAPL's revenue for FY2025 was $416,161 million
             [0000320193-25-000079 · FY2025 · as-of 2026-03-01]. This is sourced
             information for decision support, not investment advice."
```

### 4.2 A text question

```
"What risks did Apple disclose about its supply chain?"    as_of = 2026-03-01
  │
  ├─ router ...................... narrative words → route = narrative
  ├─ retrieve (company = AAPL)
  │     ├─ dense leg ............. bge-m3 query vector, cosine, top-50, knowledge_time <= as_of
  │     ├─ sparse leg ............ Postgres full-text rank, top-50, knowledge_time <= as_of
  │     └─ RRF fusion ............ score = Σ 1/(60 + rank) → top-8 to the answer step
  ├─ no model (default) → "Relevant disclosure is in Item 1A of … (as of …)"
  │  Gemini (opt-in)   → prose over the top-6 passages, told to cite and add no numbers
  └─ Answer: text + top-3 citations [accession · section]
```

### 4.3 Refusals and clarifications

```
"What is Apple's CUSIP?"               → refused  (identifier not stored, U7)
"What was Tesla's revenue in FY2025?"  → refused  (outside the 10 companies)
"Which of Walmart's suppliers …?"      → refused  (relational/graph — not built)
"What was Apple's Q3 2024 revenue?"    → clarify  (fiscal Q3 or calendar Q3?)
"JPMorgan gross margin vs Apple?"      → clarify  (a bank has no gross margin)
```

### 4.4 Ingestion, end to end

```
backfill ──► documents + blobs/ ──► facts_load ──► facts, fiscal_calendars, supersession links
                                 └─► narrative ──► chunks ──► embed_missing ──► chunks.embedding
                                 └─► headline extract ──► fixtures/u13_staged.json ──[human verifies]──► facts (preliminary)
prices (Tiingo) ──► prices, corporate_actions            [not yet run]
```

## 5. Storage

- **PostgreSQL 16 + pgvector** in Docker (`pgvector/pgvector:pg16`, host port 5433 —
  ADR-0002). One database holds everything: facts, calendars, registry, documents, chunks,
  their full-text index (GIN on `tsv`) and vector index (HNSW, cosine).
- **Blob store:** `blobs/<TICKER>/<accession>/…` on local disk, gitignored, ~477 MB.
  Raw files are never modified; everything can be rebuilt from them.
- **Fixtures:** frozen, committed inputs for offline checks (`fixtures/`), and the
  answer keys (`golden/`).

Full schema: [lld/data_model.md](lld/data_model.md).

## 6. External services

| Service | Used for | Called when | Key |
|---|---|---|---|
| SEC EDGAR (data.sec.gov, sec.gov) | Filings, submissions index, companyfacts | Ingestion only | none (User-Agent with email required) |
| Gemini API (free tier) | Press-release extraction; optional prose answers | Ingestion (U13); answers only if `generate_fn=gemini_generate` | `GEMINI_API_KEY` |
| Tiingo | Daily prices, split/dividend factors | Price backfill (not yet run) | `TIINGO_API_KEY` (empty) |
| Hugging Face (model download) | `BAAI/bge-m3` weights, first use only | First embedding call | none |

Gates and tests never call any of these (the bge-m3 model runs locally).

## 7. Security and compliance

- **Not investment advice:** posture line on every answered response (`generate.POSTURE`).
- **EDGAR fair access:** hard-coded 8 req/s pacing under the SEC's 10 req/s cap, measured
  by a sliding-window counter; the client refuses to start without a contact email.
- **Licensing:** CUSIP/ISIN deliberately not stored (licensed identifiers); vendor price
  data not redistributed; no scraping of transcript sites.
- **Secrets:** `.env` is gitignored; `.env.example` lists the keys.
- **Least privilege:** the numbers path runs as `usrag_ro` (read-only). Note: text
  retrieval in `answer()` uses whatever connection the caller passes; gate 5 passes a
  read-only one.

## 8. Where the build differs from the original design

The original design (`docs/implementation/archive/design_us.md`) remains the statement of
intent. The table below is the complete list of material differences in what is built.

| Area | Original design | As built | Why |
|---|---|---|---|
| Router | LLM classifier (§6.0) | Keyword/pattern rules | ADR-0014 |
| LLM provider | Anthropic Claude (§4.1) | Gemini free tier | ADR-0008 |
| Metric/period extraction | LLM binds template parameters (§6.2) | Keyword tables + regex in `generate.py` | Follows from ADR-0014 |
| Answer checking | Verifier extracts numbers from the model's draft; mismatch → regenerate once → abstain (§6.4) | Number answers are filled in by code, so no model touches them; `verify()` re-checks the executor's own value. No regenerate loop. Numbers inside Gemini prose are **not** checked | Simpler, but see the gap below |
| Text answers | LLM writes the answer | Off by default: returns pointers to the passages; Gemini is opt-in | Offline gates (fixtures-only rule) |
| `hybrid` route | Runs both lanes and merges | Goes to the text lane only | Not yet built |
| Segment numbers | Exact from XBRL dimensions (§3.2) | Not loaded; segment questions go to text search | ADR-0013 |
| Preliminary (8-K) figures | Loaded as `preliminary` rows | 63 rows staged (AAPL, CAT, COST); none loaded until human verification | U13, ADR-0005 |
| Prices / split adjustment | `price()` template (§6.2) | Tables empty; price questions refused | No Tiingo key |
| Chunk size | ≤ ~800 tokens (§4.5) | Token count is estimated (chars/4); real chunks reach 1,634 tokens | Measured in L2 (ADR-0016) |

**Known gap to close in L1:** prose written by Gemini can contain numbers that nothing
verifies. The prompt forbids it, but no code checks it. L1's answer grading measures
faithfulness; a numeric check on prose is a candidate addition.
