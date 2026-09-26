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

Three words you'll see everywhere:

- **SEC** — the US regulator. Public companies must file reports with it.
- **Filing** — one report. The big three: **10-K** (yearly report), **10-Q** (quarterly
  report), **8-K** (news of an important event; the earnings *press release* is attached
  to one of these).
- **RAG** — "retrieval-augmented generation": instead of an AI answering from memory, you
  first *find* the relevant material, then answer from it.

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

### Idea 2 — Two clocks: *what it's about* and *when the world knew it*

Every number and every piece of text carries two dates:

```
  CLOCK 1 — the period it describes      CLOCK 2 — when it became public
  ("revenue for Jan–Mar 2024")           (the exact second the SEC accepted the filing)
```

Here is Caterpillar's first quarter of 2024, from our real data:

```
  Jan ────── Mar 31              Apr 25                Apr 28              May 1
  │ Q1 2024 happens │            press release         a question          10-Q (the full
  │ (Clock 1)       │            filed (Clock 2)       asked "as of"       quarterly report)
                                  ▲                     this date           filed (Clock 2)
                                  │                        │                  ▲
                                  └──── visible ◄──────────┤                  │
                                                           └──── NOT visible ─┘ (it's the future)
```

Every read in the system carries an **as-of date**, and the database only returns things
whose Clock 2 is on or before it. So "what did we know on 28 April?" gets an honest answer —
the 1 May report can't leak in. This rule is built *into the database queries*, not
applied afterwards, so no code path can forget it.

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
| 07 | Measuring it | test questions, recall scores, automatic checks | `production/03_evaluation_and_testing.md` | `eval/`, `golden/`, `gates/` |
| 08+ | One per new step: observability (L1), chunking (L2), reranking (L3), graphs (L4), monitoring (L5) | | new LLDs as they're built | |

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
│   ├── glossary.md       every term, in plain words
│   ├── exercises/        optional hands-on files that check themselves
│   └── old_walkthroughs/ earlier per-phase notes, being replaced
└── implementation/   the plan: status, roadmap (what's next), future ideas, your sign-off checklist
```

Next: **01 — The raw material**.
