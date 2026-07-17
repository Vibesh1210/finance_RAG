# CURRENT PHASE — Phase 2: Ingestion (deep dive, theory → code)

This is the pre-build deep dive for the active phase (DECISIONS.md #7). Read it
before any Phase 2 code exists. When the gate goes green this file is archived
to `learn/phase_02_brief.md` and rewritten for Phase 3. Plain language
throughout; every new term is defined where it first appears.

---

## 1. What this phase is, in one paragraph

Until now the system is an empty, very opinionated filing cabinet: Phase 1
built the drawers (database tables) and the rules about what may go in them.
Phase 2 fills the cabinet with **real data** — every SEC filing our 10
companies made in fiscal 2024 and 2025, every number inside those filings,
the narrative text (risk factors, management discussion) chunked and indexed
for search, and two years of daily stock prices. The phase is done when the
gate proves the data is complete, correct against the original documents, and
**point-in-time honest** — meaning the database can answer "what did the world
know on date X" without cheating with later knowledge.

## 2. The complete pipeline, on one screen

```
                        THE INTERNET                                YOUR MACHINE
  ┌──────────────────────────────────────────────┐
  │ SEC EDGAR (free, keyless, rate-limited)      │
  │  • submissions.json   — per-company index    │──① list filings──┐
  │  • filing documents   — iXBRL HTML + Ex-99   │──② fetch────────▶│  blobs/   (raw files on disk)
  │  • companyfacts.json  — all tagged numbers   │──③ fetch────────▶│  cache
  └──────────────────────────────────────────────┘                  │
  ┌──────────────────────────────────────────────┐                  ▼
  │ Tiingo (API key)  daily prices + split/div   │──⑥──▶ ┌─────────────────────────────┐
  │ Stooq  (keyless)  cross-check only           │──⑥──▶ │        POSTGRES             │
  └──────────────────────────────────────────────┘       │ documents  ← ② registry     │
                                                          │ facts      ← ④ numbers      │
   ② every fetched filing registered ──────────────────▶ │ fiscal_calendars ← ④        │
   ④ companyfacts → facts rows + supersession pass       │ chunks     ← ⑤ text+vectors │
   ⑤ iXBRL HTML → sections → chunks → embeddings         │ prices, corporate_actions ⑥ │
   ⑦ 8-K press releases → LLM extracts 3 headline        │ facts(preliminary=true) ← ⑦ │
      numbers → HUMAN verifies every row → facts         └─────────────────────────────┘
```

Seven steps, and the order matters: you can't load facts (④) before the
filings are registered (②), and the U13 rows (⑦) only make sense once the
"official" facts exist to compare against.

---

## 3. Theory first: where financial data actually lives

### 3.1 EDGAR — the SEC's public filing system

Every US public company is legally required to file reports with the SEC
(the US markets regulator), and the SEC publishes all of them, free, at a
system called **EDGAR**. No API key, no contract, no scraping gray zone. Three
document types matter to us:

- **10-K** — the annual report. Audited, exhaustive, filed once a year.
- **10-Q** — the quarterly report. Lighter, unaudited, filed three times a
  year (the fourth quarter has no 10-Q — the 10-K covers it; remember this,
  it becomes a plot point in §3.4).
- **8-K** — "something material happened." The flavor we care about is
  **Item 2.02** ("Results of Operations") with **Exhibit 99.1** attached —
  that exhibit *is* the earnings press release, and it lands **2–4 weeks
  before** the corresponding 10-Q. That time gap is the single most important
  fact in this whole project (§3.5).
- **10-K/A, 10-Q/A** — amendments: "we're correcting something we filed."
  These are natural supersession events for our bitemporal store.

Identity on EDGAR: companies are keyed by **CIK** (Central Index Key — the
SEC's permanent company ID number), not by ticker. Tickers drift (see the XOM
story in DECISIONS.md #4); CIKs don't. Every individual filing has an
**accession number** — a globally unique ID like `0000320193-25-000073` —
which is why our `documents` table uses it as primary key and why our
downloads can be made idempotent (§4.2).

Two machine-readable indexes drive everything:

- `data.sec.gov/submissions/CIK##########.json` — a company's full filing
  history: every accession, its form type, filing date, **acceptance
  datetime** (the exact timestamp EDGAR accepted the upload — our
  `knowledge_time`, §3.3), and the primary document name.
- `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` — **every tagged
  number the company ever filed**, pre-extracted by the SEC. This is the
  gift that makes this project feasible (§3.2).

The price of "free": **fair-access rules**. At most 10 requests/second, a
`User-Agent` header containing a real contact email, back off when told.
Break them and the SEC throttles your IP. Our client hard-codes these rules —
CLAUDE.md makes bypassing the limiter a gate-failing offense.

### 3.2 XBRL — numbers that arrive as data, not as PDF archaeology

You might imagine we'll parse financial tables out of documents. We won't.
Since 2019 filings are **iXBRL** ("inline XBRL"): a normal human-readable
HTML page where every number is *also* invisibly tagged with machine-readable
metadata. The SEC aggregates all those tags into `companyfacts.json`. One
real-shaped entry:

```json
"us-gaap": {
  "RevenueFromContractWithCustomerExcludingAssessedTax": {
    "units": {
      "USD": [
        { "start": "2024-04-29", "end": "2024-07-28",
          "val": 30040000000,
          "accn": "0001045810-24-000216", "form": "10-Q",
          "fy": 2025, "fp": "Q2",
          "filed": "2024-08-28" }
      ]
    }
  }
}
```

Read that as: *"NVIDIA's revenue for the period 2024-04-29 → 2024-07-28 was
$30.04B, reported in the 10-Q with that accession number."* Four things to
absorb:

1. **concept** — the tag name (`us-gaap:...`). `us-gaap` is the standard
   dictionary of US accounting concepts. But "revenue" can hide under several
   different tags, companies switch tags between years, and 10–20% of tags
   are custom per-company extensions (`aapl:`, `nvda:`) that are **never
   comparable across companies**. This is why Phase 4 builds a hand-verified
   `metric_mappings` table instead of trusting tag names. Phase 2's job is
   only to load *all* tags faithfully — mapping comes later.
2. **unit** — USD, shares, USD-per-share. Loaded verbatim; Phase 1's
   normalizer guarantees we never rescale an XBRL value.
3. **period context** — the `start`/`end` dates. This — and *only* this — is
   the fact's period identity.
4. **the `fy`/`fp` trap** — those fields describe *the filing's* fiscal
   focus, not *the fact's* period. A 10-Q contains comparison numbers from
   last year; their `fy` says this year. **Hard rule (gate-enforced): period
   identity comes from start/end dates joined to `fiscal_calendars`; `fy`/`fp`
   are never used.** A unit test feeds a fact whose fy/fp lies about its
   dates and asserts the dates win.

### 3.3 knowledge_time — the column that makes the database honest

Phase 1's central idea, now getting real data. Every fact row carries two
kinds of time:

- **period** (`period_start`/`period_end`) — what slice of the world the
  number describes ("revenue for May–July 2024").
- **knowledge_time** — when the world *learned* the number. We define it as
  the filing's **EDGAR acceptance datetime** — the provable moment the
  document became public. Never the filing date (too coarse — a date, not a
  timestamp), never "when we downloaded it" (that's *our* time, not the
  world's).

Why so strict? Because the eventual product must answer "as of September 1,
2024, what was NVIDIA's latest reported revenue?" and be *correct about
what was knowable then*. Phase 3 builds a CI test (the look-ahead gate)
that fails if retrieval ever returns knowledge from after the as-of date.
That test is only meaningful if Phase 2 stamps every row honestly today.

### 3.4 The missing Q4 — why press releases are load-bearing

Count the filings: Q1, Q2, Q3 get 10-Qs; the year gets a 10-K. **Nobody files
a standalone Q4 report.** The 10-K contains full-year numbers; Q4 exists
publicly only in the **earnings press release** (that 8-K Exhibit 99.1). And
Ex-99 has **no XBRL tagging requirement** — its numbers are just HTML.

So without extra work, "NVDA Q4 FY2025 revenue" would be unanswerable, and
so would every question in the 2–4 week window between a press release and
its 10-Q. Two remedies, split across phases:

- Phase 4: derive Q4 = FY − Q1 − Q2 − Q3 deterministically (in SQL — never
  by an LLM, per the no-LLM-arithmetic rule).
- **Phase 2e (pin U13): the bounded headline extractor.** For each of ~80
  press releases, an LLM *reads* (extraction only — copying numbers out of
  text, zero arithmetic) exactly three values: revenue, net income, diluted
  EPS. Each becomes a facts row with `source='8K-EX99'`,
  `preliminary=true`, and `knowledge_time` = the 8-K's acceptance moment.
  **You personally verify every single row** before it enters the database
  (~1.5–2 h). "Bounded" is the design's honesty: 3 numbers × 80 releases
  with 100% human review is trustworthy; extracting whole statements from
  untagged HTML is not, so we don't.

### 3.5 Supersession — when the past gets rewritten

Companies restate. The pinned in-corpus example: **JNJ spun off its consumer
division (Kenvue)**, and later filings *recast* prior-period numbers as if
Kenvue had never been there. Now two facts claim the same (concept, period)
with different values — and **both are true in time**: one was the truth as
known then, one is the truth as known now.

The bitemporal answer: never edit, never delete. The newer accession's row is
inserted, and the older row's `superseded_by` column is set to point at it —
the one write Phase 1's `facts_append_only` trigger permits (DECISIONS.md
#5). Phase 2b runs a **supersession pass**: after loading, find every
(concept, unit, period) reported again by a later accession with a different
value and set the link. The gate demands we catch **at least one** real
supersession (JNJ/Kenvue is expected) and hand-confirm it — if none appears,
something is broken, and passing requires a written audit entry.

### 3.6 Prices — why we store the "wrong" numbers on purpose

**NVIDIA split its stock 10-for-1 in June 2024**: one $1200 share became ten
$120 shares. Price charts everywhere show the *adjusted* series (history
divided by 10) so the chart has no fake cliff. We deliberately store
**unadjusted** prices — the numbers as they actually printed each day — plus
a `corporate_actions` table holding the split factor, and adjust **at query
time**. Storing only adjusted prices would smear June 2024's knowledge back
across all of history — exactly the point-in-time sin this project exists to
avoid. Tiingo (free key) is the pinned source; Stooq (keyless) cross-checks
two tickers as an independent sanity witness.

---

## 4. Code level: what actually gets built

### 4.1 The shape (five modules under `src/us_rag/`)

```
edgar.py      ① the polite EDGAR HTTP client (limiter, UA, retries, caching)
backfill.py   ②③ walk universe → select filings in window → blobs + documents
facts_load.py ④ companyfacts → facts rows; fiscal_calendars; supersession pass
narrative.py  ⑤ iXBRL HTML → sections → chunks → embeddings → indexes
prices.py     ⑥ Tiingo backfill → prices + corporate_actions; Stooq check
headline.py   ⑦ Ex-99.1 → LLM extraction → human-verification workflow (U13)
```

### 4.2 The EDGAR client — politeness as code

Three mechanisms, all small:

- **Rate limiter.** A token bucket: a counter that refills at 10 tokens/sec;
  each request spends one; no token → the request *waits*. The cap is a
  constant, not a config knob — you cannot accidentally out-configure the
  SEC's rules. On HTTP 403 or a `Retry-After` header, sleep as told, then
  resume. The limiter counts everything it does; the gate reads those
  counters and fails on any violation.
- **User-Agent.** Every request carries `SEC_EDGAR_USER_AGENT` from `.env`
  (already set — the Phase 0 gate verified it contains an email).
- **Idempotency via the registry.** *Idempotent* = running it twice changes
  nothing the second time. Before fetching an accession, check `documents`;
  already `status='fetched'` → skip. Crash mid-backfill? Re-run; it resumes.
  The accession number's global uniqueness is what makes this trivial —
  it's the `documents` primary key.

Backfill flow per company: `submissions.json` → filter to 10-K/10-Q/8-K
inside our FY2024–25 window (per *that company's* calendar) → for each: fetch
the primary iXBRL document (plus Ex-99 exhibits for 8-Ks) → write to
`blobs/` → insert the `documents` row with its acceptance datetime. Then
fetch and cache `companyfacts.json` once per company. Roughly: 10 companies
× (2 10-Ks + 6–8 10-Qs + 8+ 8-Ks) ≈ **160–200 filings**, one-time, minutes
under the rate cap.

### 4.3 Facts load — JSON to bitemporal rows

For each companyfacts entry: resolve CIK → `company_id`, look up the
accession in `documents` (its acceptance datetime becomes `knowledge_time`),
and insert:

```
concept   = the us-gaap (or extension) tag, verbatim
value     = val, verbatim (normalizer validates: no rescaling, ever)
unit      = verbatim        period_start/end = context dates, verbatim
period_kind = 'duration' (start+end) or 'instant' (end only — balances)
source    = '10-K' or '10-Q'    knowledge_time = acceptance datetime
axis/member = segment dimension when present (e.g. "Data Center")
```

Then two follow-on passes:

- **Fiscal calendars from evidence.** Period contexts reveal each company's
  real quarter boundaries — including the 52/53-week weirdness of AAPL,
  COST, JNJ, DE, whose year-ends move annually and whose Q4 sometimes has
  14 weeks. These populate `fiscal_calendars` with `source='xbrl'` and must
  agree with Phase 1's seeds; disagreement fails the gate (it means either
  our seeds or our parsing is wrong — both worth catching loudly).
- **The supersession pass** (§3.5): group by (company, concept, axis/member,
  unit, period); where a later accession re-reports a different value, set
  the earlier row's `superseded_by`. Expected catch: JNJ/Kenvue.

The as-of query this all serves — worth keeping in your head as the point of
everything:

```sql
SELECT value FROM facts
WHERE company_id = :c AND concept = :concept AND period_end = :p
  AND knowledge_time <= :as_of          -- only what was knowable then
ORDER BY knowledge_time DESC LIMIT 1;   -- the latest of that knowledge
```

(You implemented exactly this rule in pure Python in the Phase 1 exercise.)

### 4.4 Narrative extraction — text becomes searchable

From each 10-K: Item 1 (Business), 1A (Risk Factors), 7 (MD&A — management
explaining the numbers in prose), 7A (market risk); parallel sections from
10-Qs; full bodies of Ex-99.1 releases. Found via HTML structure + heading
heuristics; the gate hand-checks boundaries on 3 filings because heading
detection is exactly the kind of thing that silently rots.

Chunking is **heading-aware**: split inside sections (~800-token pieces,
~100-token overlap so sentences straddling a cut appear whole in one chunk),
but **never merge text across a section boundary** — a chunk mixing Risk
Factors with MD&A poisons retrieval, because a match on one half surfaces
the other as noise.

Each chunk is stored with its text and **two search representations**:

- **embedding** — a 1024-number vector from the **bge-m3** model. Vectors
  put similar *meanings* near each other, so "supply chain concentration
  risk" can find a paragraph that never uses those words. → pgvector column,
  HNSW index (approximate nearest-neighbor search).
- **tsv** — Postgres full-text search: classic keyword matching, which wins
  on exact terms like "Kenvue" or "10:1 split" where vectors get vague.

Phase 3 fuses both into hybrid retrieval. Critically, every chunk inherits
its filing's `knowledge_time` — text obeys the same as-of physics as numbers.

### 4.5 Prices — small but principled

Tiingo end-of-day backfill for all 10 tickers across the window →
`prices` (unadjusted, per §3.6) and `corporate_actions` (split/dividend
factors). Gate checks: no gaps longer than 3 trading days (weekends and
holidays are fine, missing weeks are not); the NVDA split present with the
right date and factor; and unadjusted × factors ≈ Tiingo's own adjusted
series (proves our adjustment math before anything downstream trusts it);
Stooq agreement on 2 tickers.

### 4.6 U13 headline extraction — the human-gated LLM

Per 8-K Item 2.02 release: LLM (Anthropic API) reads the press-release HTML
and returns revenue, net income, diluted EPS with the exact source sentence
quoted. Code validates units/scale fail-closed (a bare "30,040" with no
"$ in millions" context is **rejected, never guessed**). Rows are staged for
review — **inserted only after you verify each one**, with
`human_verified=true` at insert time. There is no verify-later flag flip,
because the Phase 1 trigger forbids mutating rows (DECISIONS.md #5's
consequence, now live). The gate re-checks every U13 row: verified, flagged
`preliminary=true`, and `knowledge_time` strictly before the matching
quarterly filing's — proving the point-in-time window is real in our data.

---

## 5. The gate, mapped to what each check protects

| # | Check | Protects against |
|---|---|---|
| 1 | Registry counts per company-window | silently missing filings |
| 2 | 20 human spot-checks match loaded facts 100% | mapping/context bugs at load |
| 3 | Fiscal calendars complete; seeds confirmed; 53-week audit resolved | the fiscal traps (U8) |
| 4 | Section boundaries on 3 hand-checked filings; every Ex-99.1 ≥ 1 chunk | silent chunker rot |
| 5 | Price continuity; NVDA split correct; adjusted-series reconciliation | broken adjustment math |
| 6 | Zero limiter violations | fair-access breach / IP ban |
| 7 | Every U13 row verified, preliminary, time-ordered before its 10-Q | unverified LLM output |
| 8 | fy/fp-independence test | the §3.2 period-identity trap |
| 9 | ≥1 supersession found and hand-confirmed (else written audit) | bitemporal machinery that silently never fires |

## 6. Your part

**Before the build can finish** (~3.5 h total, one-time):

1. **Keys into `.env`** (5 min): `TIINGO_API_KEY` (free — tiingo.com) and
   `ANTHROPIC_API_KEY`. Both currently empty.
2. **Spot-verify 20 facts** (~1 h): for 2 facts per company, open the real
   filing on EDGAR and confirm value + period + unit → recorded in
   `fixtures/spot_checks.json`, which the gate replays forever after.
3. **Verify all ~80 U13 rows** (~1.5–2 h): each extracted headline number
   against its press release.
4. **Curate the prepared-remarks manifest** (best-effort): URLs of
   voluntarily-posted CFO commentary (e.g. NVIDIA's) — used in Phase 7.

**Learning checkpoint** — after the gate is green you should be able to
explain, in your own words: why `knowledge_time` is the acceptance datetime;
why Q4 needs special handling; what the JNJ supersession *means*; and why we
store unadjusted prices. The post-phase walkthrough (`learn/phase_02.md`)
and exercise (dissect one real filing by hand) will consolidate exactly
these.

## 7. Terms this phase introduces

**EDGAR** SEC's public filing system · **CIK** SEC's permanent company ID ·
**accession number** unique ID of one filing · **acceptance datetime** the
timestamp EDGAR accepted a filing (our knowledge_time) · **10-K/10-Q/8-K**
annual / quarterly / material-event filings · **Item 2.02 / Ex-99.1** the
earnings-press-release parts of an 8-K · **XBRL / iXBRL** machine-readable
tagging inside filing HTML · **companyfacts** SEC's pre-extracted JSON of all
tagged numbers · **concept / us-gaap tag** the standardized name of a number
· **period context** the start/end dates identifying a fact's period ·
**token bucket** rate-limiter that refills permission at a fixed rate ·
**idempotent** safe to run twice · **supersession** newer filing replaces an
older value without deleting it · **preliminary fact** press-release number
awaiting its official filing · **embedding** vector representing meaning ·
**HNSW** index for fast nearest-vector search · **tsvector** Postgres keyword
index · **unadjusted price** the price as it actually printed that day.

(These also belong in `learn/glossary.md` — added when the phase builds.)
