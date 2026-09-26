# ADR-0005: "Append-only" means a write-once `superseded_by` link, enforced by a trigger

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-11 |
| **Type** | Architecture |

## Context

Pin U11 says facts are append-only, but the design puts the supersession link (`superseded_by`) on the OLD row, and setting it is technically an UPDATE.

## Decision

The `facts_append_only` trigger forbids DELETE always and allows exactly one change per row: setting `superseded_by` from NULL once, with every other column unchanged. TRUNCATE bypasses row triggers, so the Phase 1 gate lints it out of `src/` instead (tests may use it on their throwaway database).

## Consequences

History cannot be rewritten, even by buggy code. Rows that need human sign-off (U13 press-release figures) must be verified BEFORE insert with `human_verified=true`; there is no way to flip that flag afterwards.
