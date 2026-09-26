# Production docs — the system as it is built

The engineering reference for the US Equity Financial RAG. These docs describe the
**code as it runs today**, not the original plan. Where the build differs from the
original design, the difference is written down here with the ADR that decided it.

If a doc here disagrees with the code, the code wins and the doc is a bug — fix the doc
in the same change.

## Which doc answers which question

| Question | Doc |
|---|---|
| What problem does this solve, for whom, and what counts as success? | [01_overview.md](01_overview.md) |
| What are the parts and how does a question flow through them? | [02_hld.md](02_hld.md) |
| What exactly is in each table, and how does "as of a date" work? | [lld/data_model.md](lld/data_model.md) |
| How does data get from the SEC into the database? | [lld/ingestion.md](lld/ingestion.md) |
| How is an exact number looked up or derived? | [lld/numbers_engine.md](lld/numbers_engine.md) |
| How is filing text searched? | [lld/retrieval.md](lld/retrieval.md) |
| How is a question routed, answered, checked or refused? | [lld/answering.md](lld/answering.md) |
| How do we know it works (test questions, scores, gates, CI)? | [03_evaluation_and_testing.md](03_evaluation_and_testing.md) |
| How do I set it up, load data, run checks, fix known problems? | [04_runbook.md](04_runbook.md) |
| Why is something the way it is? | [adr/README.md](adr/README.md) |

## Reading paths

- **New to the project:** 01 → 02 → the LLD for whatever you're touching.
- **Changing code:** the LLD for that component → the ADRs it links → 03 (which gates
  cover it).
- **Running it:** 04.

## Related sections

- `docs/learning_docs/` — the same system explained in plain words, for learning.
- `docs/implementation/` — status, the roadmap (what's built next), future scope, and the
  archived original design (`archive/design_us.md`), whose `§` section numbers are
  cited throughout the code.

## Conventions

- Diagrams are plain text so they read the same in a terminal, an editor and GitHub.
- "U1–U13" are the original pinned decisions from the archived execution plan
  (`docs/implementation/archive/execution_plan_us.md`, Part 0.2); "§N" refers to a section
  of the archived design. Later decisions are ADRs.
- Numbers quoted here (41,175 facts, 7,033 chunks, …) are from the current corpus load.
