# ADR-0003: `universe.json` is derived, never hand-edited

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-10 |
| **Type** | Architecture |

## Context

The 10-company list needs CIKs (SEC company IDs). Typing them by hand invites silent mistakes.

## Decision

`universe.json` is generated from `fixtures/company_tickers.json` (a frozen snapshot of the SEC's ticker file) plus the pinned constants in `src/us_rag/universe.py`, by `scripts/build_universe.py`. The Phase 0 gate re-derives it and compares byte-for-byte. The design table's CIK column is a hint only; the SEC snapshot wins, except where `CIK_OVERRIDES` pins a filing entity on purpose (ADR-0004).

## Consequences

A hand edit fails CI by construction. Changing the universe means changing the inputs and regenerating.
