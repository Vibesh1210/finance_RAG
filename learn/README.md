# Learning track

This folder exists because the project has **two goals with equal weight**: a
working system, and you being able to explain and rebuild its core ideas.

The repo map and the build plan live in `../START_HERE.md`.

## How the loop works (agreed 2026-07-12; doc layout updated 2026-09-17)

For every step from here on:

1. **Before building** — `learn/<step>_brief.md`: the concept in plain words,
   theory down to code level, the complete flow. What problem this step solves,
   why it matters, what choices we have. No unexplained jargon, ever. You read
   this BEFORE any code exists.
2. **Build** — Claude builds at full speed, to the step's gate.
3. **After the gate is green** — `learn/<step>.md`: a plain-language
   walkthrough of what was actually built, plus **one exercise** where you
   rebuild the step's core idea yourself, small enough for an evening. The
   brief is folded into this file and deleted, so this folder keeps **one file
   per step**.
4. **Q&A** — ask anything, any level, at any time. "What does X even mean" is
   always a good question. When you can explain the step back in your own
   words, it's consolidated.

The exercises are self-checking wherever possible — you run them and they tell
you if you're right, the same way the gates tell the build if it's right.

## Read in this order

| File | What it gives you |
|---|---|
| `00_the_whole_thing.md` | The entire system in plain words, about 15 minutes |
| `glossary.md` | Every term the project uses, in plain words, with examples from our own repo |
| `phase_00.md` | What Phase 0 built and why + a break-it-on-purpose exercise |
| `phase_01.md` | What Phase 1 built (the heart of the system) + the as-of exercise |
| `phase_02.md` | Ingestion — one filing → numbers + prose; the chunk-packer exercise |
| `phase_03.md` | The ruler (golden bank) + hybrid search; the RRF-by-hand exercise |
| `phase_04.md` | The exact-numbers engine; the metric-resolver exercise |
| `phase_05.md` | The conductor (router → generate → verify) = M0; the verifier exercise |
| `verification_guide.md` | The sign-off checklist: 159 items, mostly comparing a number to a filing |
| `exercises/` | Runnable, self-checking exercise files (one per step) |

## The syllabus — what each step teaches you

Every step gets: a brief (before), a walkthrough (after), one exercise (after).
Done ✅ / upcoming ⏳. The plan behind the upcoming rows: `../docs/roadmap_learning.md`.

| Step | The ideas you'll own | The exercise flavor |
|---|---|---|
| Phase 0 ✅ | Gates as robot checklists, fixtures & reproducibility, why derived files test themselves | Break the repo on purpose, watch the gate catch you |
| Phase 1 ✅ | **Bitemporal time** (what did we know, when), append-only history, fail-closed parsing, fiscal calendars, slippery identity | Implement the as-of rule yourself in pure Python |
| Phase 2 ✅ | Anatomy of SEC filings, one parse → numbers + prose, polite scraping (rate limits, fair access), idempotent pipelines, heading-aware chunking, the 8 GB embedding-memory bug | Implement the heading-aware chunk packer in pure Python |
| Phase 3 ✅ | Why you write the exam before studying (golden questions), keyword vs meaning search, hybrid merging (RRF), recall metrics, the look-ahead trap in retrieval | Implement Reciprocal Rank Fusion by hand |
| Phase 4 ✅ | Why "revenue" is ambiguous (metric mapping), SQL templates vs letting an LLM write SQL, deriving Q4 when nobody reports it, the no-LLM-arithmetic rule | Implement the metric resolver (company override + abstain) |
| Phase 5 ✅ | Routing questions to the right tool, generation with citations, verification (every number must match a record), knowing when to refuse | Implement the verifier's core (exact-match + abstention guard) |
| M0 sign-off ⏳ | Why a test set nobody checked proves nothing; freezing a baseline; what "provisional" costs you | Verify a handful of facts straight from the filings yourself |
| L1 ⏳ | Tracing (debugging from logs alone), counting cost and latency per stage, grading written answers with a second model — and testing that grader against your own grades | Read one trace file and reconstruct what the system did |
| L2 ⏳ | Chunking trade-offs: size, overlap, split answers; grading retrieval at quote level instead of section level | Chunk one filing three ways by hand, predict which finds the answer |
| L3 ⏳ | Rerankers (slow-but-smart second pass), measuring lift against cost, calling a go/no-go honestly | Score 10 chunk rankings by hand, compare with the reranker |
| L4 ⏳ | Knowledge graphs, and the meta-skill: proving you DON'T need to build something | Draw the supply-chain graph on paper from two 10-Ks first |
| L5 ⏳ | Event-driven systems, monitors, exactly-once alerts, alert precision/recall | Design one alert rule and its duplicate-prevention |

## The honest rule

If a walkthrough or brief uses a term that isn't in the glossary and isn't
explained inline, that's a bug in the document — say so and it gets fixed.
