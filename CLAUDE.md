# US Equity Financial RAG

Start every session by reading START_HERE.md and docs/implementation/status.md. Keep
status.md current (ADR-0007): update it at every step change and whenever blockers or
notable progress change.

Docs live in three sections (ADR-0019):
- docs/production/ — the system AS BUILT: overview, HLD, one LLD per component, evaluation
  and testing, runbook, ADRs (decision records; replace the old DECISIONS.md, numbers kept).
- docs/learning_docs/ — plain-language teaching for the user, organised by system part.
- docs/implementation/ — status, roadmap, current/ and completed/ step plans, future scope,
  the M0 sign-off checklist, and archive/ (the original design + execution plan, unchanged).

Code is separated into backend/ (Python source, database definitions, tests, gates,
scripts) and frontend/ (UI documentation and future browser application). Frontend-specific
designs and plans live in frontend/docs/ (ADR-0022); shared docs retain the layout above.
Run make/uv commands from the repository root, which owns Python configuration and data.

Authority order: docs/implementation/roadmap.md (WHAT is built next, and each step's spec)
> docs/production/ (HOW it is built now; if a doc disagrees with the code, the code wins and
the doc gets fixed) > ADRs (WHY) > docs/implementation/archive/ (original intent; the
"design §N" and "execution plan Phase N" comments in code point here) > status.md (state
only — never an authority). This project is self-contained; the sibling india_rag/ project
is independent and never an authority here.

Hard rules (violations fail gates):
- U8: fiscal periods are resolved from fiscal_calendars, never computed by formula.
- U11: facts are append-only, row-level bitemporal; supersession rows, never edits.
- No-LLM-arithmetic: every number in an answer comes from SQL/deterministic code.
- EDGAR client: never bypass the rate limiter; never remove the User-Agent.
- CI is fixtures-only: no external data-API calls in gates.

Git workflow (ADR-0021): work on a branch named `<step>/<topic>`; never commit to `main`
directly; merge by pull request with all four CI checks green (lint, unit, integration,
secrets). Run `make check` before pushing.

Protocol for a step: write its plan in docs/implementation/current/<step>.md; implement to
its gate (backend/gates/<step>.py, wired into `make gate`); all earlier gates stay green; any
deviation or choice is a new ADR in docs/production/adr/; update the LLD of every component
touched in the same change; [HUMAN] tasks are for the human — stop and ask. The full
definition of done is at the end of docs/implementation/roadmap.md.

Learning loop (ADR-0006 — the user is learning this domain; an equal goal):
- Learning docs are organised by system part (docs/learning_docs/00_…, §8 has the map) and
  written one at a time, each reviewed with the user before the next.
- Every learning doc follows the same shape: the problem (with a real example from our
  data) → one flow diagram to remember → walk through the flow naming the files → the rules
  → check-yourself questions with hidden answers → optional tiny exercise.
- Teach with flows: plain-text diagrams the user could redraw from memory.
- Plain language, zero unexplained jargon (glossary: docs/learning_docs/glossary.md).
  Explain the project's own labels (M0, L1, "gate", "[HUMAN]", ADR) the first time they
  appear. Answer any "what does X mean" question at any depth.
- Before building a new step (L1…L5): write its learning doc as a brief; finish it after the
  gate is green.
