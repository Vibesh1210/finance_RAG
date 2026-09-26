# LLD · Data model

Source of truth: `db/migrations/001_core.sql`, `002_ingest.sql`, `003_metrics.sql`
(applied in order by `store/migrate.py`, tracked by filename in `schema_migrations`).

## 1. Entity map

```
 companies ─┬─< tickers            (point-in-time: valid_from / valid_to)
            ├─< name_aliases       (not unique across companies: ambiguity is representable)
            ├─< identifiers        (FIGI only; CUSIP/ISIN excluded, U7)
            ├─< fiscal_calendars   (FY + Q1..Q4 per fiscal year — the only source of period dates)
            ├─< documents ─┬─< facts   (numbers; bitemporal; append-only)
            │              └─< chunks  (text; knowledge_time; tsvector; vector(1024))
            ├─< metric_mappings    (company_id NULL = default row)
            ├─< prices             (unadjusted daily closes)          [empty]
            └─< corporate_actions  (splits, dividends)                [empty]
```

## 2. Tables

### companies · tickers · name_aliases · identifiers (security master, design §4.3)

| Table | Key columns | Notes |
|---|---|---|
| `companies` | `company_id` PK, `cik` UNIQUE CHAR(10), `name`, `sector`, `fye_month_hint`, `week_52_53_calendar` | `fye_month_hint` is for humans only; real dates come from `fiscal_calendars` |
| `tickers` | PK (`company_id`, `ticker`, `valid_from`), `valid_to` NULL = current | `valid_from = 1970-01-01` means "before anything we model" |
| `name_aliases` | PK (`company_id`, `alias`) | Seeded from `store/seed.py:ALIASES` (e.g. "Apple", "JP Morgan", "John Deere") |
| `identifiers` | PK (`company_id`, `scheme`), `scheme IN ('FIGI')` | Not populated yet |

Seeded from `universe.json` (itself derived — ADR-0003; XOM pinned to the predecessor
CIK — ADR-0004).

### documents (registry, design §4.4)

| Column | Meaning |
|---|---|
| `accession` PK | SEC's unique filing ID — the idempotency key for the whole pipeline |
| `form`, `filed_date` | 10-K, 10-Q, 8-K (and /A) |
| `acceptance_datetime` | Exact SEC acceptance time → becomes `knowledge_time` of everything from this filing |
| `blob_path`, `primary_doc_url` | Where the raw file is on disk / at the SEC |
| `status` | `registered` → `fetched`; `metadata` for baselines |
| `corpus` BOOLEAN | TRUE = in the FY2024–25 corpus. FALSE = pre-corpus baseline registered only so its facts have an exact knowledge time (ADR-0020) |

Current: 389 rows (350 fetched corpus filings, 39 metadata-only baselines).

### facts (bitemporal numbers, design §4.2, pin U11)

| Column | Meaning |
|---|---|
| `fact_id` BIGSERIAL PK | |
| `company_id`, `concept` | `concept` = us-gaap tag (e.g. `Revenues`) or a pseudo-concept for press-release rows |
| `axis`, `member` | Segment dimensions — always NULL today (ADR-0013) |
| `value` NUMERIC, `unit` | Exact decimal; unit `USD`, `USD/shares`, `shares`, `pure`, … |
| `period_start`, `period_end`, `period_kind` | **Valid time**: what the number describes. `instant` facts (balance sheet) have no start |
| `knowledge_time` TIMESTAMPTZ | **Knowledge time**: acceptance datetime of the reporting filing — never the filing date |
| `accession` → documents | Provenance |
| `source` | `10-K` · `10-Q` · `8K-EX99` · `derived` (10-K/A loads as `10-K`) |
| `preliminary`, `human_verified` | TRUE for press-release rows, which are inserted only after human sign-off |
| `superseded_by` → facts | Write-once link to the row that replaced this one |

Indexes: `facts_asof_idx (company_id, concept, period_end, knowledge_time)`,
`facts_identity_idx (company_id, concept, unit, period_end, knowledge_time)`,
`facts_accession_idx`.

**Append-only trigger** (`facts_append_only`, ADR-0005): DELETE always raises; UPDATE
raises unless it sets `superseded_by` from NULL exactly once with every other column
unchanged. TRUNCATE is banned from `src/` by the Phase 1 lint.

Current: 41,175 rows, 405 supersession links, 0 preliminary rows.

### fiscal_calendars (design §4.6, pin U8)

PK (`company_id`, `fiscal_year`, `fiscal_period`); `fiscal_period IN ('FY','Q1'..'Q4')`;
`period_start`, `period_end`, `weeks` (NULL for month-based calendars), `source`
(`seed` | `xbrl`), `source_accession`, `knowledge_time`.

Seeded by hand for a few company-years (`fixtures/fiscal_seeds.json`), then re-derived
from XBRL contexts by the facts loader; a disagreement stops the load. 100 rows = 10
companies × 2 years × (FY + 4 quarters).

FY label convention: a fiscal year is named for the calendar year it **ends** in
(NVIDIA FY2025 = 2024-01-29 → 2025-01-26).

### chunks (design §4.5)

| Column | Meaning |
|---|---|
| `chunk_id` BIGSERIAL PK | |
| `accession`, `company_id`, `doc_type` | Which filing; `doc_type` = form |
| `section` | `Item 1`, `Item 1A`, `Item 7`, `Item 7A`, `Part I Item 2 (MD&A)`, `Part I Item 3`, `Part II Item 1A (Risk Factors)`, `EX-99.1`, … |
| `fiscal_context` | e.g. `FY2025 Q2`, when the filing's report date matches a calendar row |
| `knowledge_time` | Inherited from the filing |
| `text` | The chunk |
| `tsv` | Generated: `to_tsvector('english', text)` — keyword search |
| `embedding` vector(1024) | bge-m3, normalised — meaning search |

Indexes: GIN on `tsv`; `chunks_asof_idx (company_id, knowledge_time)`; HNSW on
`embedding` with `vector_cosine_ops`. Current: 7,033 rows, all embedded.

### metric_mappings (design §6.2)

`metric_key`, `company_id` (NULL = default), `us_gaap_tag` (**NULL = typed abstention**),
`unit`, `comparable`, `provenance`, `verified_by`, `valid_from`. Unique: one default per
metric; one override per (metric, company). Loaded (replace-all) from
`fixtures/metric_mappings.yaml` by `metrics.seed_metric_mappings`. 12 metrics; overrides
for AAPL/MSFT/JNJ revenue; JPM revenue `comparable=false`; JPM gross profit and cost of
revenue NULL.

### prices · corporate_actions (design §3.5, §4.7) — empty

`prices(company_id, trade_date, open, high, low, close, volume, source)` stores
**unadjusted** prices; `corporate_actions(action_type IN ('split','dividend'), ex_date,
factor, amount)`. Adjustment happens at read time so history is never rewritten.

## 3. The as-of read rule

`store/asof.py:AsOfContext` is the sanctioned way to read `facts`:

```
A row is visible at time T  ⇔  row.knowledge_time <= T
                            AND (row.superseded_by IS NULL
                                 OR the superseding row's knowledge_time > T)
```

```sql
SELECT f.* FROM facts f
LEFT JOIN facts sup ON sup.fact_id = f.superseded_by
WHERE f.knowledge_time <= :as_of
  AND (f.superseded_by IS NULL OR sup.knowledge_time > :as_of)
  [AND company/concept/period_end/axis filters]
```

Worked example (JNJ, restated by the Kenvue separation):

```
row A: H1 2023 revenue $50,276M   known 2023-07   superseded_by → B
row B: H1 2023 revenue $42,413M   known 2024-07

as_of 2024-01-01 → sees A only (B not yet known)            → $50,276M
as_of 2025-01-01 → sees B; A is hidden (its successor known) → $42,413M
```

Chains compose: if C later supersedes B, each as-of sees exactly one of A/B/C.

Writes: `insert_fact()` appends; `supersede(old, new)` sets the link after checking both
rows describe the same fact (company, concept, axis, member, unit, period) and the new one
is not known earlier.

## 4. Roles

| Role | Rights | Used by |
|---|---|---|
| `usrag` | Owner | Migrations, ingestion, tests |
| `usrag_ro` | `pg_read_all_data` — read everything, write nothing | Numbers engine and gate 5 (`db.connect_ro`) |

Connection strings: `DATABASE_URL` / `DATABASE_URL_RO` (defaults to localhost:5433).
