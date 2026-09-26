# ADR-0019: Docs restructured into production, learning and implementation sections

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-26 |
| **Type** | Process |

## Context

Docs mixed built and planned work: the execution plan still described 14 phases (several cut), the design doc described things that were built differently or not at all, STATUS.md carried a long build diary, and learning walkthroughs contained claims that no longer matched the code.

## Decision

All docs live under `docs/` in three sections. `docs/production/`: the system as built (overview, HLD, one LLD per component, evaluation and testing, runbook, and these ADRs, which replace `DECISIONS.md` with numbers preserved). `docs/learning_docs/`: plain-language teaching, organised by system part, written one section at a time. `docs/implementation/`: status, roadmap, completed and current step plans, future scope, the M0 sign-off checklist, and an archive holding the original design and execution plan unchanged. The root keeps `README.md`, `CLAUDE.md` and a short `START_HERE.md`. The Phase 0 gate's required-files list is updated to the new paths.

## Consequences

Code comments citing "design §N" still resolve (to `docs/implementation/archive/design_us.md`). Code comments citing "DECISIONS #N" were rewritten to "ADR-00NN". New decisions are new ADR files. When code changes, the matching LLD changes in the same step.
