# ADR-0001: US market build is standalone; india_rag is independent

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-10 |
| **Type** | Scope |

## Context

The project began as a delta on top of an Indian-market design. Two projects sharing docs meant neither could be read alone.

## Decision

This repo builds the US-market system as a fully standalone project (design v0.3). The sibling `india_rag/` project is independent; its documents are never an authority here.

## Consequences

Every design and plan document needed to build this system lives in this repo. Comparisons with the Indian build are informational only.
