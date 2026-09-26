# ADR-0004: XOM pinned to the predecessor CIK after the 2026-07-01 reorganization

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-10 |
| **Type** | Data |

## Context

The live SEC ticker file maps XOM to CIK 0002115436 ("ExxonMobil Holdings Corp"), a successor registrant whose first filing is an 8-K12B dated 2026-07-01 and which has no 10-K/10-Q filings. All FY2024/FY2025 filings live under the predecessor, Exxon Mobil Corp, CIK 0000034088 (checked against both entities' submissions JSON on 2026-07-10).

## Decision

`CIK_OVERRIDES` in `src/us_rag/universe.py` pins XOM to the predecessor CIK, with a `cik_note` in `universe.json`. Ticker → CIK is treated as point-in-time (design §4.3).

## Consequences

The corpus loads correctly. This case is the in-corpus proof that even "which company is this ticker" changes over time. Revisit if anything the successor files is ever ingested.
