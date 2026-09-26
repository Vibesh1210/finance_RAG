# Start here

The map of this repo and the plan for finishing it. Written for you (the human) and for
any AI session picking the project up. Plain language throughout — if a word here isn't in
`learn/glossary.md` and isn't explained on the spot, that's a bug in this file.

---

## 1. What this project is

A question-answering system over SEC filings for 10 US companies (AAPL, CAT, COST, DE, JNJ,
JPM, MSFT, NVDA, WMT, XOM), covering each company's own fiscal 2024 and 2025.

You ask in plain English; it answers with a source, or it says it doesn't know. It has two
lanes:

- **Numbers** come from a database of 41,175 figures pulled from the filings, looked up with
  pre-written SQL. The AI never calculates.
- **Text** ("what are Apple's main risks?") comes from 7,033 searchable pieces of filing
  text, found by combining meaning-search and keyword-search.

Two things make it harder than a normal document chatbot: it must never use information
that wasn't public yet on the date you ask about, and companies restate old numbers, so the
same question has a different true answer depending on when you ask it.

**Two goals, equal weight:** a working system, and you being able to explain and rebuild its
ideas.

---

## 2. The docs, and when to read each

**Read once, in this order**

| File | What it gives you |
|---|---|
| `START_HERE.md` | This file: the map and the plan |
| `learn/00_the_whole_thing.md` | The whole system in plain words, about 15 minutes |
| `learn/phase_00.md` → `phase_05.md` | How each built piece works, one per step, each with a small exercise |

**Check whenever you sit down**

| File | What it gives you |
|---|---|
| `STATUS.md` | Where we are right now: what's done, what's green, what's blocked |

**Open when you need them**

| File | What it gives you |
|---|---|
| `learn/glossary.md` | Any term you don't know, in plain words |
| `learn/verification_guide.md` | The sign-off checklist you work through (159 items) |
| `DECISIONS.md` | Why something is the way it is — 18 entries, newest at the bottom |

**The authorities — these settle arguments**

| File | Authority over |
|---|---|
| `docs/roadmap_learning.md` | **What we build next and in what order.** This is the plan |
| `docs/execution_plan_us.md` | How each piece gets built, and what its check must prove |
| `docs/design_us.md` | The design and the reasons behind it (the `§` numbers other docs cite) |

**Everything else**

| File | Purpose |
|---|---|
| `README.md` | The front page for outsiders. Thin today; rewritten in step 2 of the plan |
| `CLAUDE.md` | The working agreement for AI sessions: what to read, the rules, the loop |

**If two docs disagree:** the roadmap wins on *what's next*, the execution plan wins on
*how to build it*, the design doc wins on *why*. `STATUS.md` only reports the current state
— it is never an authority.

---

## 3. Where we are today

The first working version (called **M0**) is built: all six original build steps, every
check passing. But every score so far was measured against an answer key drafted by the AI
and **not yet checked by you**, so none of the numbers can be trusted or quoted yet.

Nothing after M0 has been started. The sign-off checklist is the one thing blocking
everything else. `STATUS.md` always has the current detail.

---

## 4. How we work — the loop for every step

1. **Brief first.** Before any code, you get `learn/<step>_brief.md`: what this step is,
   why it matters, in plain words.
2. **I build.** At full speed, to the step's check.
3. **The check runs.** Every step has a pass/fail script in `gates/`. It must pass, and all
   earlier ones must keep passing (`make gates`).
4. **Walkthrough + exercise.** `learn/<step>.md`: what was actually built, plainly, plus one
   small rebuild-it-yourself exercise (an evening at most). The brief is folded into this
   file and deleted, so `learn/` keeps one file per step.
5. **Record it.** Anything decided or deviated from goes in `DECISIONS.md`; `STATUS.md` is
   updated.
6. **Ask anything, any time.** "What does X mean" is always a fair question.

**Your part:** verifying facts against filings, curating, grading samples, making scope
calls, and the exercises. Anything marked `[HUMAN]` stops the build and waits for you.
**My part:** everything else — building, checking, and writing the docs above.

---

## 5. The plan — eight steps to the finish

The roadmap (`docs/roadmap_learning.md`) is the authority; this is the short version.

| # | Step | What gets built | Your part | Done when |
|---|---|---|---|---|
| 1 | **M0 sign-off** | Nothing new — the answer key gets checked against real filings, and price data is switched on | The 159-item checklist; a free Tiingo key | Answer key frozen, first trustworthy scores, `v0.1.0` tagged |
| 2 | **Showcase 1: README** | A front page: the problem, a diagram, real results, design choices, how to run it | Read it and correct anything that overstates | A stranger gets the project in 2 minutes without running it |
| 3 | **L1: Observability, cost, answer grading** | A record of every question (route, search scores, time, tokens, cost), a report over the test questions, and a second AI model that checks written answers stick to their sources | Grade ~20 answers by hand so we know the grader is reliable | Report shows quality *and* cost per stage; grader agreement recorded |
| 4 | **Showcase 2: Demo page + video** | One local page: question in, answer + sources + the step-by-step record out. Plus a 2-minute video | Watch it, pick the example questions | A reviewer sees it working without installing anything |
| 5 | **L2: Chunking eval** | A finer answer key (the exact sentence that answers each question) and four chunk-size variants compared side by side | Confirm ~26 quotes (about an hour) | A comparison table and a written keep-or-change decision |
| 6 | **L3: Reranker** | A slower, smarter model re-sorts the top 20 results and keeps the best 8, behind an on/off switch | Call the go/no-go | Quality gain vs added time, measured both ways |
| 7 | **L4: GraphRAG demo** | A small map of company relationships, with a source quote on every link | Sanity-check the relationships | One relationship question answered with its sources |
| 8 | **L5: Monitoring demo** | A watchlist that alerts on important new filings, without repeats | Judge which alerts were worth reading | Alerts scored for how many were useful and how many were missed |

Roughly 8–10 weeks at a learning pace. Steps 1 and 2 are days, not weeks.

**Why this order.** Step 1 comes first because every later "did it improve?" number is
meaningless against an unchecked answer key. Step 3 comes before the improvements because
it is the measuring tool they're judged with. The reranker (6) comes after the chunking work
(5) because changing chunk sizes moves the baseline it would be measured against.

**Deliberately not built:** a web server API, fine-tuning the search model, news ingestion,
conversation memory, an agent that plans multi-step research, real-time market prices, and
full production hardening. Reasons are in `DECISIONS.md` #15 and #17.

---

## 6. Rules that never bend

These are checked automatically; breaking one fails a check.

- **Fiscal periods are looked up, never calculated.** Microsoft's 2025 ended in June,
  NVIDIA's in January. A formula would silently produce the wrong quarter.
- **Stored facts are never edited or deleted.** A restated number is added as a new row
  linked to the old one, so "what did we know, and when" stays answerable.
- **The AI never does arithmetic.** Every number in an answer comes from SQL or
  deterministic code.
- **The SEC download limits are never bypassed**, and the identifying email header is never
  removed.
- **Checks run offline**, on frozen sample data — no live internet calls.
- **Nothing unverified enters the database.** AI-extracted figures wait for your sign-off.

---

## 7. Commands

```bash
make up                  # start Postgres (with vector search) in Docker
make sync                # install Python dependencies
make gate PHASE=5        # run one step's pass/fail check
make gates               # run every check built so far
make test                # unit tests
```

Each new step (L1–L5) adds its own check script in `gates/` and wires it into `make gate` as
part of that step's work.

---

## 8. Where new files go

| Thing | Location |
|---|---|
| Code | `src/us_rag/` |
| Tests | `tests/` |
| Step checks | `gates/` |
| Test questions and answer keys | `golden/` |
| Frozen sample data for checks | `fixtures/` |
| Learning material | `learn/` (one file per step, plus `exercises/`) |
| Decisions and deviations | `DECISIONS.md` (append only, newest last) |

Docs removed on 2026-09-17 (`DECISIONS.md` #18) — stale or duplicated: `CURRENT_PHASE.md`,
`phases_docs/`, `docs/random.txt`, and three `learn/phase_0N_brief.md` files. They remain in
git history if ever needed.
