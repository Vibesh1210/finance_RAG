# Phase 4 brief — the exact-numbers engine

*Plain-language, written before building (learning loop). Terms explained in place.*

## Why this phase exists

Phase 3 gave us *text* search. But the dangerous questions in finance are about
*numbers* — "what was revenue?", "what's the margin?" — and you must **never** let a
language model read a number out of a paragraph or do arithmetic in its head. That's how
RAG systems confidently state a wrong figure. Phase 4 builds the part that answers number
questions by **looking them up in the database with exact, reviewed logic** — so every
number is traceable to a filing and computed by code, never guessed.

The objective, in the plan's words: *every number the system emits is deterministic,
mapped, and provenance-carrying.*

## The four ideas

**1. A metric registry (the dictionary).** Companies tag the same idea with different
labels. "Revenue" is `Revenues` for Caterpillar but `RevenueFromContractWithCustomer…`
for Apple. A bank like JPMorgan has no "gross profit" at all. So we keep a small,
human-reviewed table — `metric_mappings` — that says, for each metric and each company,
*exactly which filing tag to read*. The language model never picks the tag; it just says
"revenue for Apple," and the registry does the rest. If a metric genuinely doesn't apply
to a company (JPMorgan gross profit), the registry says **"abstain"** — and the system
refuses rather than computing a nonsense number. This is the curation-with-judgment step
you'll review.

**2. Templates, not free-form SQL.** The model is allowed to fill in the blanks of a few
*reviewed* query shapes — "metric for company in period," "the same metric across
several companies," "the last N periods" — but it never writes database code itself. Fewer
ways to go wrong, and every query is auditable.

**3. A read-only door.** Those queries run through a database login that can *read
everything and write nothing*. Even if something went wrong, the numbers engine
physically cannot change the data.

**4. As-of correctness carries through.** Every lookup still respects the "as of" date
(from Phase 1's bitemporal model) — so "revenue as we knew it in March 2024" returns the
value known then, never a later restatement. We reuse the same point-in-time selector the
rest of the system uses.

## Two rules that never bend

- **No-LLM-arithmetic.** Every *computed* number — year-over-year change, a margin, a
  multi-year average, a derived Q4 — is produced by SQL or plain code. The model only
  *narrates* what the code computed.
- **Q4 is derived, carefully.** Companies report the full year and the first three
  quarters, but usually not Q4 on its own. For *additive* figures (revenue, net income)
  Q4 = full year − Q1 − Q2 − Q3, computed in SQL with checks that the four periods
  exactly tile the year. For *per-share* figures (EPS), subtraction is wrong (share
  counts differ), so Q4 EPS comes from the early-earnings press release or the system
  abstains — never a bad subtraction.

## Build order (slices)

Phase 4 is the biggest phase, so it's built in slices:

1. **Deterministic spine (this slice):** the registry + read-only executor + `metric_value`
   (look up one exact number, as-of, with a citation — or abstain), including JPMorgan's
   abstentions and the no-arithmetic rule.
2. Series & compare templates (last-N periods; across companies).
3. Derived metrics (year-over-year, growth rate, margins) — all computed in code.
4. Segment numbers (e.g. NVIDIA Data Center) using the axis/member columns.
5. Q4 derivation.
6. The verifier (every emitted number must exactly match a source row) + the Phase 4 gate.

## What needs you

~45 minutes at the end: **review the metric registry** (`fixtures/metric_mappings.yaml`) —
confirm each metric points at the right filing tag, and that the JPMorgan abstentions are
correct. That's the judgment step a machine shouldn't make alone.
