# Phase 5 brief — wiring it all together (= M0)

*Plain-language, before building. This is the last phase to the finish line.*

## What this phase does

Phases 2–4 built the parts. Phase 5 is the **conductor** that turns a question into a
cited, trustworthy answer — and it's where the pieces finally connect:

1. **Router** — reads the question and decides *which path* answers it: the exact-numbers
   engine (Phase 4), the text search (Phase 3), a refusal, or a "please clarify."
2. **Generation** — writes the answer using **only** the evidence that path fetched
   (retrieved passages and/or SQL results). This is the one place a language model writes
   prose — tightly fenced.
3. **Verification** — the hard gate: every number in the answer must exactly match a
   source (Phase 4's verifier). If it doesn't, regenerate once, then abstain. No unverified
   number ever reaches you.

## The router (this slice)

The router maps each question to a **typed route**:
- `metric` → the exact-numbers SQL path ("what was revenue?")
- `narrative` → text search ("what risks did they disclose?")
- `graph` → relational ("which suppliers overlap?") — refused until a later milestone
- `unanswerable` → a typed refusal with a reason (CUSIP, intraday price, a company we
  don't cover…)
- `clarify` → the question is ambiguous ("Q3 2024" — fiscal or calendar?) and needs a
  follow-up
- `hybrid` → unclear, so run both and merge

Two rules from the design:
- **Resolve the entity and the period first, deterministically.** The router never
  *guesses* what "Q3 FY2025" means — it looks it up (Phase 1's fiscal calendars) before
  deciding anything.
- **Never send a number question to text-only.** A confident wrong number is the worst
  failure in finance, so the router structurally prevents it.

**For M0 the router is rule-based** (keyword + entity + period patterns), not an AI
classifier — because it's auditable, testable, and can't be "creatively wrong." An AI
classifier is a drop-in upgrade later (DECISIONS #14). We *measure* the router against the
60 golden questions (a routing scorecard) — the design's whole point is that routing is
measured, not hoped.

## What "done" looks like (the M0 gate)

The finish line: on the full golden bank — numbers exact-match ≥ 90%, every unanswerable
correctly refused, zero look-ahead, every number cited `[filing · section · as-of]`, and
the router's accuracy recorded as a baseline. When that gate is green, **you're at M0.**

## Build order (slices)

1. **Router (this slice)** — classify + resolve entity/period first + confidence, measured
   on the 60 questions.
2. **Generation + verifier wiring** — the LLM writes over fetched evidence; the verifier
   rejects any bad number; typed refusals; the not-advice posture.
3. **The M0 gate** (`gates/phase_05.py`) — the full end-to-end run.
