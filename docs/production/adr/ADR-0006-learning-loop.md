# ADR-0006: Working mode: "I build, you consolidate"

| | |
|---|---|
| **Status** | Accepted (layout amended by ADR-0018, ADR-0019) |
| **Date** | 2026-07-12 |
| **Type** | Process |

## Context

The project has two equal goals: a working system and the human learning the domain. Watching generated code taught the human nothing.

## Decision

Every step gets a plain-language explanation before it is built, and a plain walkthrough plus a small self-checking exercise after its gate is green. A glossary defines every term; no unexplained jargon in learning material.

## Consequences

Learning material is part of the definition of done. Since ADR-0019 it lives in `docs/learning_docs/`, organised by system part.
