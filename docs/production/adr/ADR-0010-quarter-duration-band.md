# ADR-0010: Phase 1 quarter-length check widened from 85-98 to 83-111 days

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-19 |
| **Type** | Data |

## Context

The "plausible durations" check assumed every quarter is 13-14 weeks. Costco's real calendar is 12-week quarters with a 16-week Q4 (83 and 111 days), so correct data failed the check.

## Decision

Band widened to 83-111 days; the full-year band (360-372) is unchanged. An exact-membership check (83/90/97/111) was rejected because calendar-quarter companies legitimately measure 89-91 days.

## Consequences

Costco's verified quarters pass; implausible durations are still caught.
