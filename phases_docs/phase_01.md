# Phase 1 — The Data Spine: Schemas, Time, Units, Identity

**Status:** ✅ gate green (`make gate PHASE=1`, 8/8 checks; 50 pytest tests) · 2026-07-11
**Implements:** `docs/execution_plan_us.md` Phase 1 · design §4.2–§4.6, §9 (append-only)
**Decisions logged this phase:** DECISIONS.md #5

---

## 1. What Phase 1 is for (theory)

Every later phase writes into or reads from what this phase built. Four ideas
carry the whole design, and all four landed here:

1. **Bitemporality.** A financial fact has *two* times: the period it describes
   (`period_start/end` — valid time) and the moment we learned it
   (`knowledge_time`). Q3 revenue "happens" in August–October, but we learn it in
   late November from an 8-K, again in early December from a 10-Q, and possibly
   again years later from a restatement. Systems that store one value per fact
   silently overwrite history; ours stores every version and lets the query pick
   the one that was known at its `as_of` instant. That single idea is what makes
   "what did we know on 2024-11-30?" answerable — and it's why the store is
   **append-only**: an update would be history rewriting itself.
2. **Fail-closed units.** "1,240" in a filing means nothing without scale context
   — the table header decides whether it's thousands or millions. A parser that
   guesses is a 1000× error generator. Ours refuses: no scale, no answer
   (`UnitError`), and structured XBRL values pass through as exact Decimals that
   are *validated*, never transformed.
3. **Resolved fiscal time, never computed.** US fiscal calendars are per-company
   (five different FYE months in our ten names), FY labels collide (NVDA and WMT
   "FY2025" both end January 2025 on different days), and 52/53-week calendars
   make quarter lengths *data, not arithmetic* (DE FY2025 has 53 weeks). So pin
   U8: periods come from a table populated from filings; a missing period is an
   error (`FiscalGapError`), and there is no formula fallback to be wrong.
4. **Identity is point-in-time too.** Phase 0's XOM event (a nine-day-old
   holding-company reorganization) proved tickers move between CIKs in real time.
   The security master models ticker validity windows; entity resolution returns
   *all* candidates and refuses to guess when ambiguous.

## 2. What was built (file by file)

### `db/migrations/001_core.sql` + `us_rag/store/migrate.py`
One migration creates the full §4 schema: `companies`, `tickers` (validity
windows), `identifiers` (FIGI only — CUSIP/ISIN excluded by U7), `name_aliases`
(deliberately *not* unique per alias: ambiguity must be representable),
`documents` (accession-keyed registry), `facts`, `fiscal_calendars`,
`corporate_actions`, `prices` (unadjusted by design §3.5), `chunks` (tsvector
generated column + pgvector `vector(1024)` for bge-m3, HNSW index), and
`metric_mappings` (empty until Phase 4). The runner is ~40 lines: files in name
order, applied once, recorded in `schema_migrations` — no down-migrations,
mirroring the append-only philosophy at schema level. The migration also does
`CREATE EXTENSION IF NOT EXISTS vector` so *any* database it targets (the pytest
DB, CI's service DB) is self-sufficient.

### The `facts` table and its trigger (the heart of the phase)
Full §4.2 DDL: concept + optional segment axis/member, exact `NUMERIC` value,
valid-time pair with `duration|instant` kind (a CHECK requires `period_start` for
durations), `knowledge_time` (EDGAR acceptance datetime — never the filing date),
provenance (`accession`, `source ∈ {10-K, 10-Q, 8K-EX99, derived}`),
`preliminary`, write-once `superseded_by`, `human_verified`.

**The append-only paradox and its resolution (DECISIONS.md #5):** U11 demands
append-only, yet the supersession link lives on the *old* row. The
`facts_append_only` trigger squares this: DELETE always raises; UPDATE is allowed
only when `superseded_by` goes NULL→value *once* and every other column is
bit-identical (`ROW(...) IS DISTINCT FROM ROW(...)` compares all 15 columns).
TRUNCATE bypasses row triggers entirely — a fact worth knowing — so the gate
lints `TRUNCATE` out of `src/` instead. Defense in depth: python's `supersede()`
additionally verifies both rows describe the *same logical fact* (same company,
concept, axis, member, unit, period) and that the superseder isn't known earlier
than the superseded — "time travel" is a bug, not a feature.

One subtle consequence, pre-decided for Phase 2: since `human_verified` can't be
flipped after insert, **U13 rows are inserted only after the human verifies them**
— verification is a precondition of existence, not a status update.

### `us_rag/store/asof.py` — `AsOfContext`
The only sanctioned read path. The as-of rule in one SQL shape:

```sql
SELECT f.* FROM facts f
LEFT JOIN facts sup ON sup.fact_id = f.superseded_by
WHERE f.knowledge_time <= :as_of
  AND (f.superseded_by IS NULL OR sup.knowledge_time > :as_of)
```

Read it as: *you see a row if you'd learned it by T, unless you'd also learned by
T about the row that replaces it.* Supersession chains (A→B→C) compose with no
extra logic — each row hides exactly when its successor becomes known. Chunks are
simpler (no supersession): `knowledge_time <= as_of`. This is the query Phase 3's
retrieval pushdown and Phase 5's verifier both inherit.

### `us_rag/units.py`
`parse_quantity(text, header=, metric_class=)` finds the first quantity in text
and normalizes it to an exact `Decimal` inside a typed `Quantity(value, kind)`.
The rule table: inline scale words beat header scale; `%`/`bps` → ratio, never
scaled; per-share and ratio classes *reject* scale words ("EPS of $6.13 million"
is an error, not a big EPS); accounting negatives `(1,234)`; unbalanced parens
rejected; uppercase `$15M` is fifteen million but `$15m` is an error (ambiguous);
`\b` guards stop "Months" from reading as a million; and the headline rule — a
scalable number with no scale context anywhere **raises**. `normalize_xbrl()` is
the validator half: int/str/Decimal in → identical Decimal out, floats rejected
outright (tested with 2⁶³+1, a value float silently corrupts). A hypothesis
property test proves `parse(render(q)) == q` across three kinds — the two
directions of the normalizer can't drift apart.

### `us_rag/fiscal.py` + `fixtures/fiscal_seeds.json`
`resolve(conn, company_id, ticker, text)` extracts the first period expression
and answers **only from `fiscal_calendars`**. Pattern precedence: `Q3 FY2025` →
`FY2025` → `Q3 2024` → bare `2024`. The ambiguity policy returns a
`FiscalResolution` whose `interpretation` string is ready to surface in answers:

- `("CAT","Q3 2024")` → fiscal==calendar detected *from the data* (CAT's FY row
  is exactly Jan 1–Dec 31), so not ambiguous.
- `("DE","Q3 2024")` → DE's fiscal Q3 (Apr 29–Jul 28!) with `ambiguous=True`.
- bare year → majority-overlap over *stored* FY rows: calendar 2024 ≈ NVDA FY2025
  (338 days of overlap vs 28 for FY2024). Overlap uses date *subtraction* of
  stored rows — comparison, not construction; the gate lints `timedelta(`,
  `relativedelta`, `dateutil`, and `days=9x` constants out of `fiscal.py`.

The seeds (30 rows, hand-entered from filings, provenance note in the file):
NVDA FY2024/FY2025 + all four FY2025 quarters (52-week, late-January FYE), MSFT
FY2025 + quarters (month-based), AAPL FY2024 (ends 2024-09-28), WMT FY2024/FY2025
+ quarters (fixed Jan 31), CAT FY2024 + quarters (calendar), DE FY2024 + quarters
and **DE FY2025 = 2024-10-28 → 2025-11-02, weeks=53** — the in-window 53-week
year. `[HUMAN]` verification (~30 min) is still open; the real safety net is
Phase 2, which re-derives every row from XBRL contexts and fails its gate on any
seed mismatch. Seeds can never clobber `source='xbrl'` rows (the upsert's WHERE
clause).

### `us_rag/entities.py`
`resolve()` matches ticker (point-in-time via validity windows, `as_of` param)
then aliases, returns *all* candidates; `resolve_one()` raises on ambiguity with
the candidate list in the message — the clarification policy's raw material.
XOM resolves to the predecessor CIK `0000034088` (the filing entity), which the
gate asserts explicitly.

### Tests (`tests/`, 50 passing)
`conftest.py` drops and recreates `usrag_test` from migrations + seeds every
session — so **every test run is also a from-scratch migration rehearsal**. Tests
never commit; each test's connection rolls back, which keeps them isolated
without fighting the append-only trigger (uncommitted rows vanish on rollback).
Error-expectation tests wrap statements in `conn.transaction()` savepoints so one
expected DB error doesn't poison the rest of the test.

The bitemporal suite stages the canonical §4.2 scenario with synthetic rows: an
8-K preliminary fact (accepted Aug 28) superseded by the 10-Q final (accepted
Oct 30) — as-of Sep 15 you see the preliminary row flagged `preliminary=true`;
as-of Feb you see the final; before Aug 28, nothing. Plus: three-row supersession
chains, trigger blocks on UPDATE/DELETE/double-supersede, identity and
time-travel guards, and chunk as-of visibility.

## 3. The gate, check by check

| # | Check | What failure would mean |
|---|---|---|
| 1 | migrations apply + idempotent | broken DDL, or a migration that re-runs (would corrupt real data later) |
| 2 | seeds load idempotently | seed script can't be safely re-run — every later phase re-seeds |
| 3 | U8 lint on `fiscal.py` | someone added a quarter formula — the exact bug class U8 exists to kill |
| 4 | append-only source lint | an `UPDATE/DELETE/TRUNCATE facts` outside `supersede()` — U11 bypass in code |
| 5 | live trigger probe (rolled back) | the DB itself would accept history rewrites — the last line of defense down |
| 6 | seed sanity (NVDA 5 rows, DE 53wk, plausible durations) | hand-entry typos of the kind that poison every fiscal answer downstream |
| 7 | resolver canary (NVDA Q3 FY2025 → 2024-10-27; XOM → predecessor) | the two marquee behaviors of the phase regressed |
| 8 | 50-test suite green (units, fiscal, bitemporal, entities) | any of the fixture matrices broken |

## 4. Boundaries honored (what Phase 1 did *not* do)

No EDGAR calls, no real facts, no chunk content, no embeddings, no metric
mappings — those are Phases 2–4. The `fye_month_hint` on companies stayed a
*hint*; nothing reads it for logic. `metric_mappings` exists but is empty by
design. The seed rows carry `source='seed'` so Phase 2's XBRL-derived rows are
distinguishable and authoritative.

## 5. `[HUMAN]` checklist

- [ ] ~30 min: verify `fixtures/fiscal_seeds.json` against the filings (NVDA
  10-K FY2025 cover/contexts, MSFT/WMT/CAT trivially, AAPL FY2024, DE FY2024
  quarters and the FY2025 53-week claim). Phase 2 will cross-check mechanically;
  your pass catches transcription slips earlier.
- [ ] Still open from Phase 0: API keys in `.env`, universe sign-off, remote repo.

## 6. What Phase 2 consumes from here

The `documents` registry contract (accession-keyed, acceptance-datetime as
knowledge_time), `insert_fact`/`supersede` as its only write path (supersession
pass = U11 detector), `fiscal_calendars` to fill with `source='xbrl'` rows that
must match the seeds, `normalize_xbrl` as the exactness validator on every loaded
fact, and the security master to attach everything to. Phase 2 is where this
spine meets real EDGAR data — client, backfill, narrative chunks, U13 extraction,
prices.
