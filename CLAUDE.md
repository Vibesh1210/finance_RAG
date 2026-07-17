# US Equity Financial RAG

Start every session by reading STATUS.md (global state: target, phases, current,
done, blockers) and CURRENT_PHASE.md (theory-to-code deep dive of the active
phase). Maintain both (DECISIONS.md #7): update STATUS.md at every phase
transition and whenever blockers or notable progress change; when a phase's gate
goes green, archive CURRENT_PHASE.md to learn/phase_NN_brief.md and rewrite it
for the next phase BEFORE building. CURRENT_PHASE.md follows the learning rules
below — plain language, theory → code, complete pipeline flow, no unexplained
jargon.

Architecture authority: docs/execution_plan_us.md (build order) > docs/design_us.md (design).
This project is self-contained — no external documents are required. The sibling
india_rag/ project is independent; its docs are never an authority here.

Hard rules (violations fail gates):
- U8: fiscal periods are resolved from fiscal_calendars, never computed by formula.
- U11: facts are append-only, row-level bitemporal; supersession rows, never edits.
- No-LLM-arithmetic: every number in an answer comes from SQL/deterministic code.
- EDGAR client: never bypass the rate limiter; never remove the User-Agent.
- CI is fixtures-only: no external data-API calls in gates.

Protocol: read this file + the current phase in docs/execution_plan_us.md; implement
to the gate; `make gate PHASE=N`; all previous gates stay green (`make gates`);
deviations go in DECISIONS.md; [HUMAN] tasks are for the human — stop and ask.

Per-phase writeups (what was built and why, code + theory) live in phases_docs/.

Learning loop (DECISIONS.md #6 — the user is learning this domain; equal goal):
- BEFORE building phase N: write learn/phase_NN_brief.md — the concept in plain
  language, zero unexplained jargon (glossary: learn/glossary.md).
- AFTER the gate is green: write learn/phase_NN.md — plain walkthrough + ONE
  small rebuild-it-yourself exercise (self-checking where possible).
- Answer any "what does X mean" question at any depth, without jargon.
