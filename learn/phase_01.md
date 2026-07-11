# Phase 1 in plain words — the data spine

*(Terms: bitemporal, knowledge_time, as-of, append-only, supersession, trigger,
migration, fail-closed → all in `glossary.md`.)*

This is the most important phase in the whole project. Everything after it is
machinery; this is the *idea*.

## Problem 1: a number isn't enough — you need to know WHEN you knew it

Say NVIDIA's Aug–Oct quarter revenue is $35.08B.

- On **Nov 19**, nobody outside NVIDIA knows it.
- On **Nov 20** (press release), the world learns a *preliminary* number.
- On **Dec 1** (formal 10-Q filing), the *final* number arrives — occasionally
  slightly different.
- Two years later a restatement might revise it again.

A normal database stores one value and overwrites it on every change — which
quietly destroys the ability to answer "what did we know on Nov 25?" That
question is everything in finance: evaluating any past decision honestly
requires knowing what was knowable *then*. Using the December number in a
November question is called **look-ahead**, and it's how backtests lie.

**Our fix:** every fact row carries two times — the period it *describes*
(valid time) and the moment we *learned* it (knowledge_time) — and rows are
**never edited or deleted** (append-only). A correction is a *new row*, linked
to the old one ("supersession"). Old rows never vanish; they just know their
successor. Then "what did we know at time T?" becomes a mechanical rule:

> Show a row if we'd learned it by T — unless by T we'd *also* learned about
> the row that replaces it.

That one sentence is `AsOfContext` (`src/us_rag/store/asof.py`). The database
itself has a tripwire (a *trigger*) that physically rejects any UPDATE or
DELETE on facts — so even buggy future code can't rewrite history.
Newspaper-archive, not whiteboard.

## Problem 2: "1,240" means nothing by itself

Financial tables say "$ in millions" at the top and then just print `1,240`.
Elsewhere the same filing writes "EPS of $6.13" (real dollars, NOT millions) and
"grew 122%" (never scaled at all). A parser that guesses wrong is off by a
factor of a thousand — and *plausible-looking*, which is the worst kind of bug.

**Our fix:** a fail-closed normalizer. It knows scale words, table-header
inheritance, accounting negatives like "(1,234)", and which kinds of numbers are
scale-exempt — and when it has no scale evidence, it **refuses** (raises an
error) instead of guessing. Also: all math uses exact decimals, never the
"float" type — floats silently mangle very large or very precise values.

## Problem 3: "Q3 2024" doesn't mean what you think

Every company picks its own year. NVIDIA's "FY2025" is basically calendar 2024.
Walmart's "FY2025" also ends in January 2025 — on a *different day*. Deere's
"Q3 2024" is April–July. Some companies' years are counted in whole weeks, so
occasionally a year has 53 weeks and a quarter has 14.

**Our fix (rule U8):** never compute fiscal dates with a formula. There's a
table (`fiscal_calendars`) filled from what companies actually filed; the
resolver looks answers up there, and if a period isn't in the table it raises
an error rather than calculating. For ambiguous phrasings ("NVIDIA in 2024")
it picks the fiscal year with the most overlap **and says so out loud** in the
answer — resolve, but never silently.

30 calendar rows were hand-typed from real filings as a starting point
(including Deere's 53-week FY2025). Phase 2 will re-derive every row from the
filings' machine-readable data and *fail its gate* if my hand-typed rows were
wrong — the safety net for human error is mechanical.

## Problem 4: even company names are slippery

"Apple", "AAPL", "Apple Inc." — same company. "XOM" — *which* legal entity,
after last week's restructuring? The security-master tables record names,
tickers (with the dates they're valid), and IDs; the resolver returns **all**
matches and refuses to pick when a name is ambiguous. Guessing identity is how
you attach Walmart's revenue to the wrong company.

## What "tested" means here (50 tests)

Every rule above is asserted by a test the machine runs: the pinned parsing
examples, the fiscal trap matrix, the Nov-window story with synthetic rows, the
trigger rejecting history edits. Plus a *property test*: a robot generates
hundreds of random amounts and verifies that printing-then-parsing always gives
back the original — checking a law, not examples.

## Exercise 1 — build the as-of rule yourself (~30–45 min)

The heart of the phase in ~15 lines of pure Python, no database:

```
uv run python learn/exercises/asof_exercise.py
```

Open the file, implement `what_was_known()`, run until all checks print PASS.
When stuck, read the SQL in `src/us_rag/store/asof.py` and translate it. Don't
copy — the point is your fingers writing the rule once.

**You've consolidated this phase when you can answer, in your own words:**
1. Why does a correction create a new row instead of fixing the old one?
2. What goes wrong for a "what did we know on Nov 25" question in a normal
   overwrite-style database?
3. Why does the fiscal resolver refuse to compute dates it doesn't have?
