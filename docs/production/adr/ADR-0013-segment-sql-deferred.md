# ADR-0013: Segment numbers via SQL deferred; segment questions use text search for M0

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-04 |
| **Type** | Scope |

## Context

Phase 2 loaded company-level facts from SEC `companyfacts`, which has no segment breakdowns. Loading them needs a new, error-prone extraction pass over the filings' dimensional XBRL.

## Decision

Defer segment ingestion. `segment_value` is built and abstains (`no_segment_data`) until data lands. For M0 the 8 golden segment questions are answered by text search (gold = Item 7, MD&A). The Phase 4 gate's segment check is relaxed accordingly.

## Consequences

Segment questions stay answerable, but as passages, not exact numbers. Tracked in `docs/implementation/future_scope.md`.
