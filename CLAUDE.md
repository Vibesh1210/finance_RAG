# US Equity Financial RAG

Start every session by reading START_HERE.md (the doc map + the plan) and STATUS.md
(global state: target, steps, current, done, blockers). Maintain STATUS.md (DECISIONS.md
#7, amended by #18): update it at every step transition and whenever blockers or notable
progress change.

Authority order: docs/roadmap_learning.md (WHAT is built next, post-M0) >
docs/execution_plan_us.md (HOW each piece is built) > docs/design_us.md (design + reasons)
> STATUS.md (state summary only — never an authority). This project is self-contained — no
external documents are required. The sibling india_rag/ project is independent; its docs
are never an authority here.

Hard rules (violations fail gates):
- U8: fiscal periods are resolved from fiscal_calendars, never computed by formula.
- U11: facts are append-only, row-level bitemporal; supersession rows, never edits.
- No-LLM-arithmetic: every number in an answer comes from SQL/deterministic code.
- EDGAR client: never bypass the rate limiter; never remove the User-Agent.
- CI is fixtures-only: no external data-API calls in gates.

Protocol: read this file + the step's spec (docs/roadmap_learning.md for L/Showcase steps,
docs/execution_plan_us.md for build detail); implement to the gate; `make gate PHASE=N`;
all previous gates stay green (`make gates`); deviations go in DECISIONS.md; [HUMAN] tasks
are for the human — stop and ask. Each new step adds its own gates/ script and wires it
into `make gate`.

Learning loop (DECISIONS.md #6 — the user is learning this domain; equal goal):
- BEFORE building a step: write learn/<step>_brief.md — the concept in plain language,
  zero unexplained jargon (glossary: learn/glossary.md).
- AFTER the gate is green: write learn/<step>.md — plain walkthrough + ONE small
  rebuild-it-yourself exercise (self-checking where possible), then fold the brief into it
  and delete the brief, so learn/ holds one file per step.
- Answer any "what does X mean" question at any depth, without jargon. Explain the
  project's own labels too (M0, L1, "gate", "[HUMAN]") the first time they appear.
