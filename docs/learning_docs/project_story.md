# The project story — how to explain and defend this project

For rehearsing: what to say when someone asks "what did you build, and why does it matter?"
— plus honest answers to the challenges people will raise. Read `00_how_to_understand_this_project.md`
first; this doc assumes its three ideas (two lanes, two clocks, one "no").

---

## 1. The 30-second answer

> "It's a question-answering system over SEC filings, deliberately narrow: 10 companies
> over two fiscal years, picked because together they contain every trap that breaks a
> financial chatbot — different fiscal calendars, a bank where 'gross margin' doesn't
> exist, a stock split, a restatement. It answers exact numbers from the SEC's own data
> with the source filing, answers text questions with hybrid search, never uses
> information that wasn't public on the date asked, and refuses rather than guesses.
> Scaling to more companies is running the same pipeline on more SEC data — the hard part
> was making it *correct*, and I built the test suite to prove it, including a check that
> fails if any future document leaks into a historical answer."

The shape of it, if you'd rather speak from a picture:

```
  PROBLEM                        WHAT I BUILT                          HOW I KNOW IT WORKS
  naive finance chatbots   ──►   two lanes (exact numbers / search) ──► 60 test questions + 25 number checks
  get numbers silently           two clocks (as-of every read)          automatic checks per build step
  wrong, use the future,         one "no" (refuse / ask back)           a look-ahead test that fails on any leak
  and guess when unsure
```

---

## 2. "Can it only answer numbers for a specific period?"

No — correct the premise first. What it can do:

| It can… | Example |
|---|---|
| Give exact numbers with the source filing | "Apple's FY2025 revenue" → $416,161M + the filing's ID |
| Compute changes, growth, margins and Q4 — in code | "NVIDIA's Q4 FY2025 revenue" → full year − Q1 − Q2 − Q3 |
| Answer **as of any past date** | "What did we know on 28 April 2024?" — nothing from the future |
| Handle restatements | J&J revenue *as first reported* vs *as restated* — both correct, by date |
| Answer text questions | "What supply-chain risks did Apple disclose?" → the filing passages |
| Refuse or ask back instead of guessing | "Apple's Q3 2024?" → "fiscal or calendar quarter?" |

What is limited is the **scope** (10 companies, 2 years) — not the capability.

---

## 3. "Why only 10 companies and 2 years?"

Because the scope is a **test bench, not a toy**. Each company was picked as a trap:

```
  Microsoft, NVIDIA, Apple …   five different fiscal year-ends ("FY2025" = different months)
  Deere                        a 53-week year (one quarter is longer than the others)
  JPMorgan                     a bank — "gross margin" doesn't exist
  NVIDIA                       a 10-for-1 stock split inside the window
  Johnson & Johnson            a restatement — the same number changed after the fact
  ExxonMobil                   its SEC identity changed mid-2026 (new holding company)
```

Every trap the system must survive is inside the bench. Adding company #11 is mostly
running the same pipeline on more data.

---

## 4. "Would it scale?"

Yes — and name the real costs, which is what makes the answer credible:

- **The source is complete.** The SEC's EDGAR covers every US listed company in the same
  formats. The company list is one config file; every loading step can be re-run safely.
- **The real work:**
  - checking the per-company dictionary of "which filing tag means revenue" — quick for
    most companies, slow for unusual ones like banks;
  - embedding time — 7,033 text pieces for 10 companies runs on a laptop; 500 companies
    would need a GPU or a hosted embedding service.
- **The design already has seams for it:** raw files stored by filing ID, search behind
  one interface, a documented plan to swap in a dedicated search engine.

---

## 5. "Why is 'an exact number for a period' even hard?"

Because most real financial questions *are* "what was X for company Y in period Z, and how
did it change?" — and that is exactly where general AI tools fail silently:

- they pick the wrong quarter (NVIDIA's "Q3 FY2025" ended in October **2024**);
- they use information that wasn't public yet;
- they produce a confident wrong number, with nothing to tell you it's wrong.

Getting *that* right — and saying no when it can't — is the valuable part. Breadth is the
easy part.

---

## 6. Questions people will ask you (with answers)

<details>
<summary><b>"Can you just add more documents — say intraday prices — and it'll answer?"</b></summary>

Not automatically. An answer needs three things: the **data** (stored with both clocks), a
**lane** that can use it exactly, and a **route** that sends the question there.

- New **text** (transcripts, news) is nearly free: the existing pipeline chunks and embeds
  it and search finds it. The hard part is licensing, not code.
- New **numbers** (prices) need the numbers lane: a table, a loader, a lookup function, a
  router rule, test questions. Search must never produce a number.

Daily prices are half-built (table and loader exist; the free key and the lookup don't).
Intraday prices are excluded mainly because the data is licensed and paid.
</details>

<details>
<summary><b>"Could you add documents about something unrelated — like cricket?"</b></summary>

The *technique* is general; this *system* is specialised. The database requires every text
piece to belong to one of the 10 companies and an SEC filing, so cricket wouldn't even load.
Forced in, simple text questions would work, but cricket statistics would be unchecked
numbers, the finance router would misread words like "earn" and "risk", and answers would
end with "not investment advice". The right design for several subjects is separate
collections, with the router picking the subject first.
</details>

<details>
<summary><b>"Why not let an LLM do more? Wouldn't that be more accurate?"</b></summary>

An LLM makes the system **understand and explain** better; it doesn't make numbers more
accurate — the code does that. So the rule is: the LLM may help with words (understanding
the question, rewriting it for search, writing the text answer, grading answers) but never
produce or calculate a number. Where it writes prose, its numbers must be checked — and
measuring whether switching it on actually helps is part of the next step (L1).
</details>

<details>
<summary><b>"How do you know it's correct?"</b></summary>

A written exam fixed *before* tuning: 60 questions with known answers (40 text, 20
numbers) plus 25 exact number checks, and an automatic check per build step that must stay
green. The look-ahead check runs every question at its historical date and fails if any
document from the future appears. And honestly: the answer key hasn't been verified by a
human yet, so the scores are provisional until that sign-off is done.
</details>

<details>
<summary><b>"Why not use a standard RAG framework?"</b></summary>

The hard parts here aren't the parts frameworks provide. No framework gives you "only what
was public on this date", fiscal calendars that differ per company, restatements kept side
by side, or "a bank has no gross margin". Those had to be designed; the search itself is a
small part (Postgres with pgvector, about 200 lines).
</details>

---

## 7. Weaknesses to own — say them before you're asked

| Weakness | What you say |
|---|---|
| The scores aren't verified | "The answer key was drafted from the same data; a human sign-off freezes it. Until then I call every score provisional." |
| Text answers aren't graded | "Numbers are checked exactly; prose isn't yet. The next step adds an AI grader, tested against my own hand-grading first." |
| No live demo | "Hosting the database and models is a cost trap for a personal project; a local demo page and a recorded video are planned." |
| Small corpus | "Some techniques — like a knowledge graph — may show little benefit at this size. I'll measure it and say so either way." |
| Trend questions aren't wired up | "The numbers engine can compute series and growth, but the answering layer only handles one period or one comparison per question yet." |

Interviewers trust a candidate who names the limits first more than one who claims none.

---

## 8. What changes this story over time

Each finished step adds a line you can say:

| After | You can add |
|---|---|
| M0 sign-off | real, human-verified numbers instead of "provisional" |
| L1 | "I measure cost and latency per step, and grade prose answers for faithfulness" |
| Demo page | "here's a 2-minute video" |
| L2 | "I tested chunk sizes against the exact answer sentences, not just the right section" |
| L3 | "I measured what a reranker buys, in quality and in time, and decided with numbers" |
| L4, L5 | "I proved whether a graph earns its place" · "it watches new filings and alerts, without duplicates" |

Keep this doc updated as each step lands.
