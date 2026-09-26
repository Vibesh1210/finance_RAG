# ADR-0020: Corpus selection, facts load scope, and Q4 calendar closure

| | |
|---|---|
| **Status** | Accepted (recorded retroactively on 2026-09-26) |
| **Date** | Decided during Phase 2 (July 2026); written down 2026-09-26 |
| **Type** | Data |

## Context

Phase 2 code (`ingest/backfill.py`, `ingest/facts_load.py`, `db/migrations/002_ingest.sql`)
cited "DECISIONS.md #9" for these rules, but that entry was never written; the number was
later reused for an unrelated scope decision (now ADR-0009). This ADR records what the code
has done since Phase 2, so the rules have a real home. No behaviour changes.

Three questions needed a pinned answer:
1. Which filings belong to the corpus, when every company's fiscal year starts on a different date?
2. Which XBRL facts get loaded, given that `companyfacts` holds every fact a company ever filed?
3. How is a Q4 row created in `fiscal_calendars` when no filing reports Q4 on its own?

## Decision

**Corpus window per company.** The window is [FY2024 start, FY2025 end], where both dates
come from that company's own annual XBRL contexts (the most frequently reported ~52-week
window for each fiscal-year label). The result is cross-checked against the hand-typed
fiscal seeds; a mismatch stops the load (`CorpusError`), never silently resolved.

- **Periodic filings** (10-K, 10-Q and their /A amendments): included when the period they
  report ends inside the window.
- **Event filings** (8-K, 8-K/A): included when accepted between the FY2024 start and the
  acceptance of the FY2025 10-K (the "corpus close"). A pure period-window cut would miss
  the Q4 FY2025 earnings release, which is filed after the fiscal year ends.

**Facts load scope.** Load every (concept, unit, period) group that at least one corpus
filing reports: all the corpus entries, plus the latest entry from before the corpus as the
"as-reported-then" baseline. The baseline's filing is registered in `documents` as
metadata-only (`corpus = FALSE`, no blob) so its knowledge time is exact. Gate registry
counts only count `corpus = TRUE`.

**Q4 calendar closure.** A Q4 calendar row is the part of the reported fiscal year after
the reported Q3: its boundaries come from reported dates (a set difference of reported
boundaries), never from a calendar formula (pin U8).

## Consequences

- Restatements of pre-corpus periods can be detected, because the old value is loaded as
  a baseline (this is how the JNJ/Kenvue restatement surfaces).
- Result on the current corpus: 389 documents (350 fetched, 39 metadata-only baselines),
  41,175 facts, 405 supersession links, 100 fiscal-calendar rows.
- `documents.corpus` must be used to count or chunk corpus filings; metadata-only rows have
  no blob.
