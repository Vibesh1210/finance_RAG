> **Old walkthrough — being replaced.** Parts of this no longer match the code; see `README.md` in this folder before relying on it.

# Phase 4 in plain words — the exact-numbers engine

*(Terms: metric registry, us-gaap tag, read-only role, abstain, derived, Q4 derivation,
verifier, no-LLM-arithmetic → `glossary.md`.)*

Phase 3 searches *text*. But the dangerous questions in finance are about *numbers*, and
you must **never** let a language model read a number out of a paragraph or do arithmetic
in its head — that's how these systems state a confident wrong figure. Phase 4 answers
number questions by looking them up with exact, reviewed logic.

## Idea 1: a dictionary from "what people say" to "what the filing calls it"

Companies tag the same idea differently — Caterpillar's revenue is `Revenues`, Apple's is
`RevenueFromContractWithCustomer…`, and a bank like JPMorgan has *no gross profit at all*.
So there's a small, human-reviewed table (`metric_mappings`): for each metric and company,
exactly which filing tag to read. The language model never picks the tag; it just says
"revenue for Apple." If a metric genuinely doesn't apply to a company, the table says
**abstain** — and the system refuses rather than computing a nonsense number.

## Idea 2: templates, not free-form database code; and a door that can't write

The model is allowed to fill in the blanks of a few *reviewed* query shapes ("metric for
company in period," "across companies," "last N periods") — it never writes SQL itself.
And those queries run through a database login that can **read everything and write
nothing**. Even a bug can't corrupt the data.

## Idea 3: every computed number is computed by code, with a receipt

Year-over-year, growth rates, margins, a derived Q4 — all done in exact decimal code, each
carrying a **computation record** (e.g. `(130497 - 60922) / 60922 = 1.142…`). The model
only *narrates* what the code computed. This "no-LLM-arithmetic" rule deletes the most
embarrassing failure class in one stroke.

## Idea 4: Q4 is derived, carefully

Companies report the full year and the first three quarters, but usually **not Q4 on its
own**. For *additive* figures (revenue, net income): `Q4 = FY − Q1 − Q2 − Q3`, computed in
code, but only after checking the four periods cleanly tile the year. For *per-share*
figures (EPS): subtraction is **wrong** (share counts differ across quarters), so Q4 EPS
comes from a preliminary press release or the system **abstains** — never a bad
subtraction. Balance-sheet items (assets): the year-end value *is* the Q4 value.

## Idea 5: a verifier that refuses to be lied to

Before any number is emitted, a **verifier** checks it exactly matches the executor's
value (allowing narrated rounding — "$46.9%" for 0.4690…), that its citation is the right
filing, and that a number claimed for an *abstaining* metric is rejected outright. This is
the hard gate the answer layer (Phase 5) leans on.

## What the JPMorgan example teaches

Ask for JPMorgan's gross margin and the system **abstains** — because a bank has no gross
profit, so the margin's ingredient is missing, so the margin can't be computed. The
refusal isn't a special case bolted on; it *falls out* of the registry saying "no mapping"
and the abstention propagating up through the division. Correct behaviour by construction.

## What "verified" means here

The Phase 4 gate is green (6/6): the 25-question SQL bank matches exactly, Q4 derivation is
proven (NVIDIA Q4 FY2025 = FY − ΣQ1–Q3 = $39,331M), JPMorgan abstains, and the
no-arithmetic rule is enforced. The gold values are real filing figures but stay
*provisional* until you confirm them (the guide) and review the registry (~45 min).

## Exercise — the metric resolver (~30 min)

The precedence-and-abstain rule at the heart of the registry, in pure Python:

```
uv run python learn/exercises/phase04_resolve_exercise.py
```

Implement `resolve()` until the checks pass. When stuck, read `pick_mapping` in
`src/us_rag/query/metrics.py`.

**You've consolidated this phase when you can answer, in your own words:**
1. Why does the language model pick the *metric name* but never the *filing tag* or the
   arithmetic?
2. Why is Q4 EPS *not* just `FY − Q1 − Q2 − Q3`?
3. How does "JPMorgan gross margin" end up as a refusal rather than a made-up number?
