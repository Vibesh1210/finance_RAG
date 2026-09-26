# ADR-0014: The M0 router is rule-based, not an LLM classifier

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-06 |
| **Type** | Architecture |

## Context

Design §6.0 specifies an LLM classifier to decide which path answers a question.

## Decision

Build the router deterministically: resolve company and period first, then keyword/pattern rules produce a typed route with a confidence and a reason. It is measured against the golden bank; the result is recorded as the M0 baseline.

## Consequences

Auditable and unit-testable; no model call, quota or flakiness in the most safety-critical decision; it structurally prevents a number question from going to text-only search. An LLM classifier remains a drop-in upgrade behind the same `RouteDecision` interface. Note: the router's expected labels in the M0 gate come from a helper in `gates/phase_05.py`, not human labels.
