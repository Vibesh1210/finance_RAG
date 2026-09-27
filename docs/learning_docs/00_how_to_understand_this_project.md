# How to understand this project

**Read this first.** It gives you the whole system in one picture, the three ideas that
explain almost every design choice, and the plan for learning the rest one part at a time.

About 20 minutes. Every diagram is meant to be *redrawn from memory* later — that's the
test of whether it stuck.

---

## 1. The project in one breath

> Ten US companies. Every official report they filed with the SEC over two years. You ask
> a question in plain English; you get an **exact, sourced** answer — or an honest
> **"I can't answer that, because…"**.

Words you'll see everywhere:

- **SEC** — the US regulator for stock markets. Public companies must file reports with it,
  and anyone can read them for free on its website (called **EDGAR**).
- **Filing** — one report sent to the SEC. The names (10-K, 10-Q, 8-K) are just the SEC's
  form numbers.
- **RAG** — "retrieval-augmented generation": instead of an AI answering from memory, you
  first *find* the relevant material, then answer from it.

### The three kinds of report

| Form | In plain words | How often | What's in it |
|---|---|---|---|
| **10-K** | The **annual report** | Once a year, ~1–2 months after the year ends | The full year: audited financial statements, the business description, **risk factors** (Item 1A), management's discussion of results (Item 7) |
| **10-Q** | The **quarterly report** | 3 times a year — after quarters 1, 2 and 3 | The quarter: unaudited statements, a shorter management discussion, updated risks |
| **8-K** | A **"something important happened" notice** | Whenever it happens, within ~4 business days | One event: a new CEO, a big deal — or, most often for us, **quarterly results**: the earnings **press release** is attached to an 8-K (as "Exhibit 99.1") |

How they fit into one company's year — Caterpillar 2024, from our data:

```
Q1 ends ──► 8-K press release (Apr 25) ──► 10-Q full report (May 1)
Q2 ends ──► 8-K press release          ──► 10-Q full report          (same pattern)
Q3 ends ──► 8-K press release (Oct 30) ──► 10-Q full report (Nov 6)
Q4 ends ──► 8-K press release (Jan 30) ──► 10-K ANNUAL report (Feb 14)   ← no 10-Q for Q4
```

Two things in that picture explain parts of the system you'll meet below:

1. **The press release always comes first.** For a few days or weeks it is *all* the
   public knows. That's exactly why the two clocks matter (Idea 2).
2. **There's no 10-Q for the fourth quarter.** The 10-K covers the whole year instead, so
   nobody ever files "Q4 revenue" as its own number. The system has to work it out as
   full year − Q1 − Q2 − Q3 — the NVIDIA example in trap 1.

---

## 2. Why this is harder than a normal document chatbot

The quick version of this project takes an afternoon: put the filings in a search index,
fetch some paragraphs, let an AI write the answer. In finance that version is dangerous,
and it fails in five specific ways. Each one shaped a part of the system:

```
  TRAP                                    REAL EXAMPLE FROM OUR DATA                     THE DEFENCE
  ─────────────────────────────────────   ───────────────────────────────────────────   ──────────────────────────
  1 The AI does maths, silently wrong     NVIDIA never reports Q4 on its own:            numbers come from code,
                                          130,497 − 26,044 − 30,040 − 35,082 = 39,331   never from the AI
  2 It uses the future                    Asked "as of 28 Apr 2024", it must not see     every read filtered to
                                          Caterpillar's report filed 1 May 2024          "public by that date"
  3 It thinks the past never changes      Johnson & Johnson H1-2023 revenue:             old values are kept,
                                          $50,276M as first reported, $42,413M later     never overwritten
  4 It computes things that don't exist   JPMorgan is a bank — it has no "gross          a per-company dictionary
                                          profit", so no gross margin                    that can say "doesn't apply"
  5 It thinks a year is a year            Microsoft's FY2025 ends June 2025,             a table of real dates per
                                          Apple's Sept 2025, NVIDIA's Jan 2025           company — never a formula
```

**The key thing about trap 1:** a wrong number *looks exactly like a right one*. No error,
no crash. Most bugs announce themselves; this one doesn't. That's why the whole system is
built so the AI never touches a number.

---

## 3. The three ideas — remember these and you can rebuild the rest

> ### Two lanes, two clocks, one "no".

### Idea 1 — Two lanes: numbers are *looked up*, words are *searched*

```
                          ┌────────────────────────────────────────────┐
                    ┌────►│ NUMBERS LANE                                │
                    │     │ "What was Apple's revenue in FY2025?"       │
  question ─► ROUTER│     │ exact lookup in a database of tagged figures│──► $416,161 million
  (picks a lane)    │     └────────────────────────────────────────────┘      + source
                    │     ┌────────────────────────────────────────────┐
                    └────►│ WORDS LANE                                  │
                          │ "What supply-chain risks did Apple list?"   │──► the passages that
                          │ search through pieces of filing text        │    say so + source
                          └────────────────────────────────────────────┘
```

Why two? Numbers need to be **exact** — search is approximate by nature, so it must never
produce a number. Words need to be **found** even when the question uses different words
than the filing — a database lookup can't do that. Each lane is bad at the other's job.

### Idea 2 — Two clocks: *what it's about* and *when the world could know it*

Every number and every piece of text in the system carries **two dates**:

```
  CLOCK 1 — what time period it is ABOUT        CLOCK 2 — when the public could first READ it
  "revenue earned Jan–Mar 2024"                  "the SEC accepted the report on 25 Apr 2024"
```

**Start with an exam.** You sit an exam in March; the results come out in May.

```
  March                        April                        May
  ┌──────────────┐                                          ┌──────────────┐
  │ exam happens │                                          │ results out  │
  │  (Clock 1)   │                                          │  (Clock 2)   │
  └──────────────┘                                          └──────────────┘
                    someone asks in April:
                    "what was your score?"  ──►  honest answer: nobody knows yet
```

The exam already *happened* (Clock 1 is in the past), but the result wasn't *public*
(Clock 2 is still in the future). Any answer given in April that uses the score is
cheating — it uses information from the future.

**Now the same thing with a company.** Caterpillar's first quarter of 2024 was published
twice — a short press release first, the full quarterly report (a 10-Q) a week later.
Same quarter, so same Clock 1; different Clock 2:

```
                              CLOCK 1 (what it's about)    CLOCK 2 (when it became public)
  Press release (8-K)         Jan–Mar 2024                 25 April 2024
  Full report (10-Q)          Jan–Mar 2024                 1 May 2024

  Question "as of 28 April 2024"  →  may use the press release   (25 Apr ≤ 28 Apr)
                                  →  may NOT use the 10-Q        (1 May is after 28 Apr — the future)
```

A normal database stores only Clock 1 ("this is Jan–Mar revenue"), so it can't tell those
two apart and would happily use the 10-Q. This system stores both.

**The rule, in one line:** every question carries an **as-of date**, and the database only
returns things whose **Clock 2 is on or before that date**. The rule is written *inside*
the database queries themselves, not applied afterwards, so no piece of code can forget it.

> Why finance cares so much: if you test an investing idea on past data and it can "see"
> reports that weren't out yet, it looks brilliant on paper and fails with real money.
> That mistake is called **look-ahead**.

And because the past can change (trap 3), nothing is ever overwritten:

```
  row A  JNJ H1-2023 revenue  $50,276M   public Jul 2023   ──replaced by──►  row B
  row B  JNJ H1-2023 revenue  $42,413M   public Jul 2024

  as of Jan 2024  →  $50,276M   (B didn't exist yet)
  as of Jan 2025  →  $42,413M   (B is known, so A steps aside)
```

Both answers are correct — they answer different questions ("what did they say *then*"
vs "what do they say *now*").

### Idea 3 — One "no": when it can't be exact, it refuses or asks

```
  question ─► can I identify the company?        no ─► "which company?" / "not one of the 10"
               can I pin the exact period?        no ─► "fiscal Q3 or calendar Q3?"
               does this metric exist for them?   no ─► "a bank has no gross margin"
               do I have the data, as of then?    no ─► "not available as of that date"
               is it something we store at all?   no ─► "CUSIP / intraday price / call Q&A not stored"
                            │
                           yes to all ─► answer, with its source
```

A system that guesses is worse than one that says no, because you can't tell its guesses
from its facts. Refusing and asking back are *answers* here, and they are tested as
carefully as the numbers.

---

## 4. The whole machine on one page

Two halves. The **back room** stocks the shelves once. The **front desk** serves each
question and only reads.

```
 BACK ROOM — stocking the shelves (runs once)          FRONT DESK — serving a question (every time)

  SEC website                                           question + as-of date
     │ polite downloader (max 8 requests/second)                 │
     ▼                                                           ▼
  ┌───────────────────┐                                   ┌───────────┐
  │ ① RAW MATERIAL     │                                   │ ⑥ ROUTER   │── "no" ──► refusal / question back
  │ filings + tagged   │                                   └─────┬─────┘
  │ numbers file       │                                   ┌─────┴──────┐
  └─────┬───────┬─────┘                                    ▼            ▼
        │       │                                   ┌───────────┐ ┌───────────┐
        │       │ ③ GETTING DATA IN                 │④ NUMBERS  │ │⑤ WORDS    │
        ▼       ▼                                   │   LANE    │ │   LANE    │
  ┌───────────────────────────────────┐             └─────┬─────┘ └─────┬─────┘
  │ ② THE STORE (one database)         │◄── reads only ───┘             │
  │  numbers, each with two clocks     │◄── reads only ─────────────────┘
  │  text pieces, each with two clocks │                  │            │
  │  company calendars, name lists     │                  ▼            ▼
  └───────────────────────────────────┘             exact number    passages
                                                    + checker       (+ AI prose, optional)
                                                          └─────┬─────┘
                                                                ▼
                                                    ANSWER + sources + "not investment advice"

                        ⑦ MEASURING IT: 60 test questions with known answers + automatic checks,
                           run against the whole thing to prove each part still works
```

The circled numbers are the seven parts. Each gets its own learning doc (section 8).

---

## 5. Follow one question — the numbers lane

> "What was Apple's total net sales for fiscal year 2025?"  — as of 1 March 2026

```
 step                                  what happens                                   where in the code
 ────                                  ────────────                                   ─────────────────
 1 find the company      "Apple" matches the name list → AAPL                         query/router.py
 2 pick the lane         money words + a company + a period → numbers lane            query/router.py
 3 name the metric       "net sales" → revenue   (a keyword table, no AI)             query/generate.py
 4 name the period       "fiscal year 2025" → FY2025                                  query/generate.py
 5 turn it into dates    Apple FY2025 = 29 Sep 2024 → 27 Sep 2025 (looked up, not     fiscal.py
                         calculated — Apple's year ends on a Saturday, not month-end)
 6 find Apple's word     the dictionary says Apple files revenue under the tag        query/metrics.py
   for "revenue"         "RevenueFromContractWithCustomer…", not "Revenues"
 7 read, as of the date  rows public by 1 Mar 2026, not replaced → 416,161,000,000    store/asof.py
 8 check it              the value, its source and comparability are checked           query/verify.py
 9 write the sentence    by a template — code, not AI:
      "AAPL's revenue for FY2025 was $416,161 million
       [0000320193-25-000079 · FY2025 · as-of 2026-03-01]. This is sourced
       information for decision support, not investment advice."
```

That long code in brackets is the **accession number**: the SEC's unique ID for the exact
filing the number came from. Anyone can look it up.

## 6. Follow one question — the words lane

> "What risks did Apple disclose about its supply chain?"  — as of 1 March 2026

```
 1 pick the lane        "risks", "disclose" → words lane                                  query/router.py
 2 search two ways, both limited to Apple and to text public by 1 Mar 2026:              query/retrieve.py
      by MEANING  — the question is turned into a list of 1,024 numbers that
                    captures its meaning (an "embedding"); the 50 closest text
                    pieces win, even if they use different words
      by KEYWORD  — the 50 pieces that best match the actual words
 3 merge the two lists  a piece near the top of EITHER list scores well;                 query/retrieve.py
                        near the top of BOTH scores best → keep the best 8
 4 answer               AI off (the default): "Relevant disclosure is in Item 1A           query/generate.py
                        of <Apple's 10-K accession> …" — a pointer, not an answer
                        AI on (Gemini): a written answer from the best 6 pieces,
                        told to cite and to add no numbers of its own
```

"Item 1A" is the **Risk Factors** section of a 10-K. Filings have standard sections, and
the text is cut into pieces (**chunks**, roughly a page each) that never cross from one
section into another.

---

## 7. What is honestly not finished

You should know these before trusting any score:

- **The answer key hasn't been checked by a human.** The 60 test questions and their
  answers were drafted by the AI from the same data being tested. Until you check them
  (the sign-off checklist), every score is "provisional".
- **With the AI switched on, numbers inside its prose are not checked.** Number answers
  are safe (code writes them). Prose answers rely on the AI obeying "add no numbers".
  L1 starts measuring this.
- **Some parts are thinner than designed:** exact segment figures (like NVIDIA's Data
  Center revenue) aren't loaded, so those questions go to the words lane; press-release
  figures await your verification; prices aren't loaded (no Tiingo key).

The complete list: `docs/production/02_hld.md`, section 8.

---

## 8. The map — the parts, and how you'll learn each one

Each learning doc is the plain-words twin of an engineering doc. Read the learning doc to
understand; open the production doc when you want the exact detail.

| # | Learning doc (plain words) | What you'll own after it | Engineering twin | Code |
|---|---|---|---|---|
| 00 | **How to understand this project** | the big picture (this doc) | `production/02_hld.md` | — |
| 01 | The raw material | what's inside an SEC filing, and the 4 things it won't give you | `production/01_overview.md` | `blobs/` |
| 02 | The store | two clocks, never erasing, company calendars, company names | `production/lld/data_model.md` | `store/`, `fiscal.py`, `entities.py` |
| 03 | Getting data in | polite downloading, numbers vs text, chunking, embeddings | `production/lld/ingestion.md` | `ingest/` |
| 04 | The numbers lane | the metric dictionary, Q4 by subtraction, "doesn't apply" | `production/lld/numbers_engine.md` | `query/metrics.py` |
| 05 | The words lane | meaning search vs keyword search, merging rankings | `production/lld/retrieval.md` | `query/retrieve.py` |
| 06 | Answering | the router, the templates, the checker, refusing well | `production/lld/answering.md` | `query/router.py`, `generate.py`, `verify.py` |
| 07 | Measuring it | test questions, recall scores, automatic checks | `production/03_evaluation_and_testing.md` | `eval/`, `golden/`, `backend/gates/` |
| 08 | **How changes get checked** | branches, pull requests, CI, unit vs integration tests | `production/03_evaluation_and_testing.md` §6 | `.github/`, `backend/tests/conftest.py` |
| 09+ | One per new step: observability (L1), chunking (L2), reranking (L3), graphs (L4), monitoring (L5) | | new LLDs as they're built | |
| — | **Project story** (`project_story.md`) | how to explain and defend the project; answers to the hard questions | `production/01_overview.md` | — |

Status: **00 written.** 01–07 are written one at a time, each reviewed with you before the
next. The old phase walkthroughs in `old_walkthroughs/` are raw material for them and get
deleted as each new doc replaces them.

---

## 9. How we'll learn each part

```
 ┌──────────────┐    ┌──────────────┐    ┌───────────────┐    ┌──────────────┐    ┌──────────┐
 │ 1 I write the │──►│ 2 you read   │──►│ 3 check        │──►│ 4 explain it │──►│ 5 I fix   │──► next part
 │ doc for one   │   │ flows first, │   │ yourself       │   │ back in your │   │ whatever  │
 │ part          │   │ then the text│   │ (answers are   │   │ own words, or│   │ was       │
 │               │   │              │   │ hidden below)  │   │ redraw a flow│   │ unclear   │
 └──────────────┘    └──────────────┘    └───────────────┘    └──────────────┘    └──────────┘
```

Every learning doc follows the same shape, so you always know where you are:

1. **The problem** this part solves — with a real example from our data.
2. **The flow** — one diagram you should be able to redraw.
3. **Walk through it** — the flow step by step, naming the file that does each step.
4. **The rules** it must never break, and why.
5. **Check yourself** — questions with hidden answers.
6. **Optional hands-on** — a tiny exercise (in `exercises/`) if you want to feel it in code.

**How to read the diagrams:** boxes are things (a part, a table, a file); arrows are data
moving; a word on an arrow says what moves or why. Read top-to-bottom, left-to-right.

Any word you don't know: `glossary.md`. Any question at all, any time — "what does X mean"
is always a good question.

---

## 10. Check yourself

Try each in your head (or on paper) before opening the answer.

<details>
<summary><b>1.</b> Why does the numbers lane never use search, and never let the AI write the number?</summary>

Search is approximate — it finds *similar* things, and "similar" is useless for a number
that must be exact. And an AI can produce a wrong number that looks exactly like a right
one, with no error to warn you. So numbers are looked up exactly and written into the
answer by code.
</details>

<details>
<summary><b>2.</b> A question is asked "as of 28 April 2024". Caterpillar's 10-Q was filed on 1 May 2024. Can the answer use it?</summary>

No. Its Clock 2 (when it became public) is after the as-of date, so from the question's
point of view it's the future. The press release filed on 25 April *is* visible.
</details>

<details>
<summary><b>3.</b> J&J's first-half 2023 revenue is $50,276M in one place and $42,413M in another. Which one is wrong?</summary>

Neither. $50,276M is what J&J reported in July 2023; after separating its consumer-health
business (Kenvue) it restated the same period as $42,413M in July 2024. The system keeps
both rows and shows whichever was the latest known *as of* the question's date.
</details>

<details>
<summary><b>4.</b> Why does "JPMorgan's gross margin" get a refusal-style answer instead of a number?</summary>

Gross margin = gross profit ÷ revenue, and a bank has no gross profit — the concept
doesn't apply. The metric dictionary says "doesn't apply" for JPMorgan, and that "no"
passes up through the division, so no number can be produced.
</details>

<details>
<summary><b>5.</b> Which lane answers "What risks did NVIDIA disclose?", and what do you get back with the AI switched off?</summary>

The words lane. With the AI off you get a pointer — "the relevant disclosure is in Item 1A
of filing …" — plus the sources. With the AI on, you get a written answer built only from
the best passages.
</details>

<details>
<summary><b>6.</b> Redraw from memory: the three ideas, in six words.</summary>

**Two lanes, two clocks, one "no".** Numbers looked up / words searched · what it's about /
when it was known · refuse or ask rather than guess.
</details>

---

## 11. Where everything lives

```
docs/
├── production/       the engineer's reference: how the system is built (HLD, LLDs, ADRs, runbook)
├── learning_docs/    this folder: the same system in plain words, one part at a time
│   ├── project_story.md  how to explain and defend the project (for interviews)
│   ├── glossary.md       every term, in plain words
│   ├── exercises/        optional hands-on files that check themselves
│   └── old_walkthroughs/ earlier per-phase notes, being replaced
└── implementation/   the plan: status, roadmap (what's next), future ideas, your sign-off checklist
```

Next: **01 — The raw material**.
