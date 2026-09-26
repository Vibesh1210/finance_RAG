# ADR-0012: Phase 3 started while Phase 2's human-only checks were still open

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-31 |
| **Type** | Process |

## Context

Phase 2's five mechanical checks passed; the four red ones were all human or API-key tasks (spot-checks, prices, U13 verification, JNJ countersign). The corpus was fully built and embedded.

## Decision

Begin Phase 3 before Phase 2 is fully green. Guardrails: quant answer-key values stay provisional until the spot-checks land; `make gates` showing phase 2 red is expected; retrieval is not tuned until the golden bank is frozen.

## Consequences

Engineering continued on real data. Every score measured since is provisional until M0 sign-off.
