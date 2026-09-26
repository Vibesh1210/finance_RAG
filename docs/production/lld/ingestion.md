# LLD · Ingestion

Everything that moves data from the SEC (and Tiingo) into the database. Offline; never
runs in gates. Order matters:

```
1 backfill ──► 2 facts_load ──► 3 narrative (+ embed) ──► 4 headline (U13) ──► 5 prices
   documents,      facts,           chunks,                  staged JSON →          prices,
   blobs/          fiscal_calendars chunks.embedding         [human] → facts        corporate_actions
                   supersession links
```

## 1. EDGAR client — `ingest/edgar.py`

Fair access enforced by construction (design §3.1):

| Mechanism | Detail |
|---|---|
| User-Agent | Required, must contain `@`; construction raises `FairAccessError` otherwise |
| Pacing | One request per 0.125 s (8/s), under the SEC's 10/s cap. The cap is a module constant; there is no config path to raise it |
| Measurement | A 1-second sliding window counts sends; any second with ≥10 sends increments `violations`. Stats are written to `blobs/_edgar_stats.json`; gate 2 check 6 asserts zero |
| Retries | Up to 5 tries. 403/429/5xx honour `Retry-After`, else exponential backoff (1, 2, 4, 8 s) |

Endpoints used: `submissions/CIK##########.json` (+ paginated pages),
`api/xbrl/companyfacts/CIK##########.json`, archive files, and the EDGAR-generated filing
index page (to find EX-99 exhibits).

## 2. Backfill — `ingest/backfill.py`

Per company:
1. Load `submissions` and `companyfacts` (cached under `blobs/`; `--refresh` refetches).
2. **Corpus window** = [FY2024 start, FY2025 end] from the company's own annual XBRL
   contexts, cross-checked against the fiscal seeds (mismatch → `CorpusError`). ADR-0020.
3. **Select:** 10-K/10-Q (+/A) whose report period ends inside the window; 8-K (+/A)
   accepted between FY2024 start and the FY2025 10-K acceptance.
4. **Fetch + register:** primary document (and EX-99.* exhibits for 8-Ks, listed in a
   per-filing `_manifest.json`) → `blobs/<TICKER>/<accession>/`; row in `documents`.

Idempotent: a `fetched` document whose blob exists is skipped. CLI:
`uv run python -m us_rag.ingest.backfill [--tickers …] [--dry-run] [--refresh]`.

## 3. Facts load — `ingest/facts_load.py`

```
companyfacts.json ──iter_entries──► entries (10-K/10-Q forms only; values parsed as Decimal)
                  ──select_rows───► corpus entries + latest pre-corpus baseline per identity group
                  ──insert_rows───► facts (knowledge_time = filing acceptance)
                  ──derive_calendar► fiscal_calendars (source='xbrl'; must match seeds)
                  ──supersession_pass► superseded_by links
```

Hard rules:
- **`fy`/`fp` are never read.** A fact's period is its context start/end dates only
  (companyfacts' `fy`/`fp` describe the *filing*, not the fact; trusting them files a
  2017 quarter as "FY2019"). Gate 2 check 8 feeds a lying `fy`/`fp` and asserts dates win.
- **Exactness:** JSON parsed with `parse_float=Decimal`; `units.normalize_xbrl` asserts
  values pass through unchanged. A contradictory duplicate (same accession + period,
  different value) is fatal.
- **Identity group** = (concept, unit, period_start, period_end).
- **Supersession pass (U11):** within each group, in knowledge order, a newer row with a
  *different* value supersedes every older still-current row. `8K-EX99` rows take part
  (a 10-Q that differs from the press release supersedes it); `derived` rows never do.
- **Q4 calendar rows** are the closure of the reported year after the reported Q3 —
  from reported boundaries, never a formula (ADR-0020).

CLI: `uv run python -m us_rag.ingest.facts_load [--tickers …]`.

## 4. Narrative — `ingest/narrative.py`

```
HTML ─blocks_from_html─► text blocks (drops ix:header, script, style, display:none)
     ─find_headings────► "Item 1A", "Part II Item 1A", … (TOC rows and page-numbered lines rejected)
     ─extract_*_sections► section → paragraphs
     ─chunk_paragraphs─► chunks (≤ ~800 est. tokens, ~100 overlap, never crossing a section)
     ─INSERT chunks────► with knowledge_time = filing acceptance
embed_missing ─────────► bge-m3 vectors for chunks with embedding IS NULL
```

| Filing | Sections kept |
|---|---|
| 10-K | Item 1, Item 1A, Item 7, Item 7A |
| 10-Q | Part I Item 2 (MD&A), Part I Item 3, Part II Item 1A (Risk Factors) |
| 8-K | EX-99.* exhibit bodies, whole (never the 8-K boilerplate) |

**Chunker:** greedy packing of paragraphs up to `TARGET_TOKENS = 800`; an oversized
paragraph is split into sentences; on overflow, the last ~`OVERLAP_TOKENS = 100` of the
previous chunk is carried into the next. Token count is **estimated** as `len(text)//4`,
so real chunks (bge-m3 tokenizer) reach 1,634 tokens — L2 measures this (ADR-0016).

**Embeddings:** `BAAI/bge-m3` (1024-d, normalised), CPU by default, batch 8, max 2,048
tokens so no chunk is truncated (ADR-0011). Env overrides: `US_RAG_EMBED_DEVICE`,
`US_RAG_EMBED_BATCH`, `US_RAG_EMBED_MAXLEN`.

Idempotent per accession (already-chunked filings are skipped); empty 10-K/10-Q section
extractions are reported, not swallowed. CLI:
`uv run python -m us_rag.ingest.narrative [--tickers …] [--embed]`.

## 5. Headline extraction (U13) — `ingest/headline.py`

Press releases (8-K Ex-99.1) carry no XBRL tags, so the preliminary numbers that appear
2–4 weeks before the 10-Q can only be read from text. Division of labour:

```
LLM READS       Gemini copies revenue / net income / diluted EPS VERBATIM, with the source sentence
CODE NORMALISES units.parse_quantity → exact Decimal; a number without a stated scale is rejected
HUMAN VERIFIES  every staged row against the release; "verified": true
CODE INSERTS    only if every row is verified; source='8K-EX99', preliminary=TRUE, human_verified=TRUE
```

Workflow: `extract` → `fixtures/u13_staged.json` → human review → `normalize` → `insert`
(`uv run python -m us_rag.ingest.headline {extract|normalize|insert|list}`).
`insert` refuses if any row is unverified and re-checks that the stored value still
matches its text. Spacing 6.5 s between calls; retries on 429/5xx.

**State:** 63 rows staged for AAPL (24), CAT (27), COST (12); 25 of them carry
extraction errors (value not found or rejected by the normaliser). The other seven
companies were not extracted (free-tier quota). Nothing inserted.

## 6. Prices — `ingest/prices.py` (not yet run)

Tiingo daily prices → `prices` (unadjusted) + `corporate_actions` (splits, dividends).
Adjustment happens at query time. A reconciliation re-derives split-adjusted returns from
our rows and compares them with Tiingo's adjusted series (tolerance 0.5%, dividend
ex-dates excepted); Stooq is a cross-check. Needs `TIINGO_API_KEY`. CLI:
`uv run python -m us_rag.ingest.prices [--tickers …] [--refresh]`.

## 7. Units normaliser — `units.py`

Used by U13 and for any text quantity:

| Input | Result |
|---|---|
| `"$1,240 million"` | 1,240,000,000 |
| `"(1,234)"` with header `$ in millions` | −1,234,000,000 |
| `"$6.13"` as per-share | 6.13 (scale-exempt; a scale word here is an error) |
| `"350 bps"` | 0.035 |
| `"1,240"` with no scale anywhere | **rejected** (`UnitError`) |

Inline scale beats header scale. All arithmetic in `Decimal`.
