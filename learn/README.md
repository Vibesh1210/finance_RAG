# Learning track

This folder exists because the project has **two goals with equal weight**: a
working system, and you being able to explain and rebuild its core ideas.

## How the loop works (agreed 2026-07-12)

For every phase from here on:

1. **Before building** — the deep dive: the concept in plain words, theory
   down to code level, the complete flow. What problem this phase solves, why
   it matters, what choices we have. No unexplained jargon, ever. You read
   this BEFORE any code exists. While a phase is active it lives at the repo
   root as `CURRENT_PHASE.md` (next to `STATUS.md`, the global state file);
   when the gate goes green it's archived here as `learn/phase_NN_brief.md`
   (DECISIONS.md #7).
2. **Build** — Claude builds at full speed (technical writeup goes to
   `phases_docs/phase_NN.md` as before).
3. **After the gate is green** — `learn/phase_NN.md`: a plain-language
   walkthrough of what was actually built, plus **one exercise** where you
   rebuild the phase's core idea yourself, small enough for an evening.
4. **Q&A** — ask anything, any level, at any time. "What does X even mean" is
   always a good question. When you can explain the phase back in your own
   words, it's consolidated.

The exercises are self-checking wherever possible — you run them and they tell
you if you're right, the same way the gates tell the build if it's right.

## Read in this order

| File | What it gives you |
|---|---|
| `glossary.md` | Every term the project uses, in plain words, with examples from our own repo |
| `phase_00.md` | What Phase 0 built and why + a break-it-on-purpose exercise |
| `phase_01.md` | What Phase 1 built (the heart of the system) + the as-of exercise |
| `exercises/` | Runnable exercise files |

## The syllabus — what each phase teaches you

Every phase gets: a brief (before), a walkthrough (after), one exercise (after).
Done ✅ / upcoming ⏳.

| Phase | The ideas you'll own | The exercise flavor |
|---|---|---|
| 0 ✅ | Gates as robot checklists, fixtures & reproducibility, why derived files test themselves | Break the repo on purpose, watch the gate catch you |
| 1 ✅ | **Bitemporal time** (what did we know, when), append-only history, fail-closed parsing, fiscal calendars, slippery identity | Implement the as-of rule yourself in pure Python |
| 2 ⏳ | Anatomy of SEC filings (10-K/10-Q/8-K), XBRL (machine-readable numbers), polite scraping (rate limits, fair access), idempotent pipelines, real supersessions (JNJ), stock-split adjustment | Fetch and dissect one real filing by hand; find one number in the raw XBRL |
| 3 ⏳ | Why you write the exam before studying (golden questions), embeddings, keyword vs meaning search, hybrid merging (RRF), recall metrics, the look-ahead trap in retrieval | Write 5 golden questions yourself; hand-score one retrieval run |
| 4 ⏳ | Why "revenue" is ambiguous (metric mapping), SQL templates vs letting an LLM write SQL, deriving Q4 when nobody reports it, the no-LLM-arithmetic rule | Map one metric across 3 companies by reading their XBRL tags |
| 5 ⏳ | Routing questions to the right tool, generation with citations, verification (every number must match a record), knowing when to refuse | Trace one question end-to-end on paper before running it |
| 6 ⏳ | What an API is, tracing/observability (debugging from logs alone), counting cost per query, caches and why invalidation is hard | Read one trace file and reconstruct what the system did |
| 7 ⏳ | Ingesting messy news feeds, deduplication, recency vs relevance | Add one RSS source end to end |
| 8 ⏳ | Rerankers (slow-but-smart second pass), conversation state, surfacing conflicting numbers honestly | Score 10 chunk rankings by hand, compare with the reranker |
| 9 ⏳ | Fine-tuning embeddings, A/B evaluation, shadow deployments & rollback drills | Run the A/B eval and call the go/no-go yourself |
| 10 ⏳ | Knowledge graphs, and the meta-skill: proving you DON'T need to build something | Draw the supply-chain graph on paper from two 10-Ks first |
| 11 ⏳ | Agents: planning loops, tool budgets, why unbounded agents are dangerous | Be the agent: solve one multi-hop question manually, logging your "tool calls" |
| 12 ⏳ | Event-driven systems, monitors, exactly-once alerts | Design one alert rule and its duplicate-prevention |
| 13 ⏳ | Ops maturity: backups you've actually restored, reconciliation, runbooks | Run the restore drill yourself, unassisted |

## The honest rule

If a walkthrough or brief uses a term that isn't in the glossary and isn't
explained inline, that's a bug in the document — say so and it gets fixed.
