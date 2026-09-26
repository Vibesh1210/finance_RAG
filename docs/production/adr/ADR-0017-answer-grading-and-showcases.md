# ADR-0017: Answer grading added to L1; README and demo page added as showcase steps

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-17 |
| **Type** | Scope |

## Context

The verifier checks numbers, but nothing grades the text of written answers. The project should also read well as a portfolio piece.

## Decision

L1 adds an LLM judge (faithfulness and relevance), calibrated against ~20 hand-graded answers before its scores are quoted; it never grades numbers, ideally uses a different model, and runs in a report command only (gates stay offline). Showcase 1: README rewrite after M0 sign-off. Showcase 2: a local demo page plus a ~2-minute video after L1 (not the cut web API).

## Consequences

Estimate moves to ~8-10 weeks. An agent/tool-calling proof of concept was considered and not added.
