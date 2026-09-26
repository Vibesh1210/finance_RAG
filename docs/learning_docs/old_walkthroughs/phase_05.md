> **Old walkthrough — being replaced.** Parts of this no longer match the code; see `README.md` in this folder before relying on it.

# Phase 5 in plain words — the conductor (= M0)

*(Terms: router, generation, verifier, abstain/clarify/refuse, posture, M0 gate →
`glossary.md`. This is the finish line.)*

Phases 2–4 built the parts. Phase 5 is the **conductor** that turns a question into a
cited, trustworthy answer — and it's where the pieces finally connect.

## Idea 1: decide the path before doing anything (the router)

The router reads a question and picks *how* to answer it:
- `metric` → the exact-numbers engine ("what was revenue?"),
- `narrative` → the text search ("what risks did they disclose?"),
- `unanswerable` → a typed refusal with a reason (CUSIP, intraday price, a company we
  don't cover),
- `clarify` → the question is ambiguous ("Q3 2024" — fiscal or calendar?),
- `graph`/`hybrid` → relational (deferred) / unclear.

Two rules: it **resolves the company and period first** (never guesses what "Q3 FY2025"
means — it looks it up), and it **can never send a number question to text-only** (a
confident wrong number is the worst finance failure). For M0 the router is a set of
auditable rules, not an AI classifier — and it routed all 60 golden questions correctly.

## Idea 2: the language model writes prose, never numbers

- For a **number** question, the answer is *templated* straight from the deterministic
  engine: "NVIDIA's revenue for FY2025 was $130,497 million [citation]." No model touches
  the figure.
- For a **narrative** question, the model (Gemini) synthesises prose from the retrieved
  passages *only*, and is told to cite them and invent no numbers.

So the one place a model writes is tightly fenced — over evidence we fetched, for prose,
never for arithmetic.

## Idea 3: the verifier is a hard gate, not a suggestion

Every number in an answer must exactly match what the engine computed (rounding for
narration allowed), cite the right filing, and — crucially — **a number claimed for a
metric that should have abstained is rejected**. On a mismatch: regenerate once, then
abstain. No unverified number ever reaches you.

## Idea 4: refuse and clarify are first-class answers

"What is Apple's CUSIP?" → a clean refusal with the reason. "What was NVIDIA's revenue in
2024?" → a clarification (fiscal vs calendar). And every substantive answer ends with a
**not-advice posture** line: this is sourced decision-support, never a directive. Knowing
when *not* to answer is as important as answering.

## What "M0" means — and its one honest caveat

The M0 gate is green (7/7): quant exact-match **94%** (≥ 90% required), 100% correct
refusals, every number cited, zero look-ahead, the JPMorgan behaviours, and the router
baseline recorded. Live, end-to-end, the system now takes a question and returns a cited
answer — number, comparison, refusal, clarification, or a real grounded narrative.

The caveat: this is green on **provisional** gold values. The system is proven to
*behave* correctly; confirming the underlying numbers against the filings
(`verification_guide.md`) is what turns "passes its own tests" into "trustworthy" — and
triggers the real M0 sign-off (the `v0.1.0` tag).

## Exercise — the verifier's core (~25 min)

The safety net in pure Python:

```
uv run python learn/exercises/phase05_verify_exercise.py
```

Implement `verify()` until the checks pass. When stuck, read `src/us_rag/query/verify.py`.

**You've consolidated this phase (and the project) when you can answer, in your own words:**
1. Why is a number's answer *templated* from the engine while a narrative answer is
   written by the model?
2. What are the two ways the verifier stops a bad number reaching the user?
3. Why is "M0 gate green" not yet the same as "M0 signed off"?
