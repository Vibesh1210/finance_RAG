# ADR-0007: A maintained status file as the entry point for state

| | |
|---|---|
| **Status** | Amended by ADR-0018 and ADR-0019 |
| **Date** | 2026-07-17 |
| **Type** | Process |

## Context

Any human or AI picking up the repo needed one place to learn the current state.

## Decision

A status file is maintained and updated at every step change and whenever blockers change. (The original decision also created `CURRENT_PHASE.md`; ADR-0018 removed it.)

## Consequences

Since ADR-0019 the status file is `docs/implementation/status.md`. It reports state only and is never a design authority.
