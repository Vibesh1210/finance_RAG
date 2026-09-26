# Learning roadmap — beyond M0

*Decided 2026-08-13 (ADR-0015); chunking evaluation added as L2 on 2026-09-17
(ADR-0016); answer grading, README and demo page added 2026-09-17 (ADR-0017). This
supersedes the "stop at M0" commitment (ADR-0009) with a
**learning-optimized** selection of the later work. It is an authority on WHICH post-M0
work is committed and in WHAT order, and it is the spec for each step (details pulled in
from the original phases 6, 8, 10 and 12 so nothing else needs reading). How the system is
built today: `docs/production/`. Original design intent (the `§` numbers):
`docs/implementation/archive/design_us.md`.*

## At a glance

| Step | Build | Done when |
|---|---|---|
| **Now — M0 sign-off** | Verification checklist (`docs/implementation/m0_signoff_checklist.md`) + Tiingo key | Golden bank frozen, baselines recorded, `v0.1.0` tagged |
| **Showcase 1** README | Rewrite `README.md`: the problem, a diagram, M0 results, key design choices, how to run | A stranger understands the project in ~2 minutes without running it |
| **L1** Observability + cost + answer grading | A trace per question; a quality-and-cost report; an LLM judge for text answers, checked against hand-graded answers | Report shows quality (incl. answer faithfulness) *and* time/tokens/cost per stage |
| **Showcase 2** Demo page + video | Local demo page over `answer()` (answer, sources, trace) + a ~2-minute video in the README | A reviewer sees it working without installing anything |
| **L2** Chunking eval | A quote-level answer key + a side-by-side chunk-size experiment | Comparison table + written keep/change decision |
| **L3** Reranker | Cross-encoder over fused top-20 → top-8, on/off flag | On/off comparison (both answer-key levels) + go/no-go |
| **L4** GraphRAG POC | Small company-relationship graph, source quote on every edge | One relationship question answered with edge citations |
| **L5** Monitoring POC | Watchlist + alerts from the daily 8-K feed | Alerts deduplicated, cited, scored for precision/recall |

**Standing rule from Showcase 1 onward:** every L's exit includes adding its result to the
README's results table. Re-record the demo video after L5.

## Why this exists

The project has two equal goals: a working system **and** the human learning the domain
(ADR-0006). After M0, the choice of what to build next is now driven by **learning
value**, not product completeness. The target skill narrative:

> *"I built a RAG from data ingestion → **chunking** → hybrid retrieval → **reranking** →
> **GraphRAG**, instrumented it for **observability**, and can **evaluate any RAG pipeline
> on performance — including whether its answers stick to the sources — and cost."*

A secondary goal (ADR-0017): the project must be **legible as a portfolio piece**
— a reviewer who won't install anything should still see what it does and how well. That
is what the two Showcase steps are for.

Every L item below is RAG-specific and advanced. The two biggest post-M0 phases are
**deliberately cut** because they teach little that transfers to RAG skills:

- **A web API (phase 6's API half)** — that's web engineering, not RAG. Observability is
  learned by instrumenting the pipeline directly (no server needed). *The Showcase 2 demo
  page is not this:* a single local page calling `answer()` directly — no endpoints, cache,
  auth or hosting.
- **Embedder fine-tuning (phase 9)** — a specialized ML loop, and design-optional
  (decision-gated). Skipping it costs nothing on the RAG-skills axis.

Also deferred (not learning-dense enough right now, or cost/infra traps): news +
conversation + conflict-surfacing (phase 7 / part of 8), real-time market data, and the
full production hardening (phase 13).

## Mapping to the existing plan

| Item | Existing phase (subset used) | What we take |
|---|---|---|
| Showcase 1 · README | *New* — not in the original plan | portfolio-grade README with measured results |
| L1 · Observability + cost + answer grading | Phase 6 (minus the API) + *new* answer grading (design §10.1 has no answer-text eval) | per-query tracing, cost/latency accounting, LLM-as-judge faithfulness |
| Showcase 2 · Demo page + video | *New* — not in the original plan; phase 6's API stays cut | local demo page + recorded walkthrough |
| L2 · Chunking eval | *New* — extends Phase 3's eval harness; tests design §4.5's chunk parameters | quote-level answer key + chunk-size experiment |
| L3 · Reranker | Phase 8 (reranker only) | cross-encoder second pass + measured lift |
| L4 · GraphRAG POC | Phase 10 (POC scope) | a small entity/edge graph + one relational answer |
| L5 · Monitoring POC | Phase 12 (POC scope) | daily-filings watchlist alerts, dedup, precision/recall |

## The ordered plan

### Prerequisite — sign off M0 (days)
Run the verification pass (`docs/implementation/m0_signoff_checklist.md`) + add the Tiingo key. This makes
the golden bank **frozen and trustworthy**, which is what lets every "did it improve?"
number below actually mean something. Tag `v0.1.0`.

### Showcase 1 — README (~1 day)
- **Goal:** the repo explains itself to someone who will only read the front page.
- **Why now:** M0 sign-off is the first moment the project has real (non-provisional)
  numbers to show. The current README is 18 lines, uses internal codes (U8, U11) and
  still describes the 14-phase plan.
- **Build:** rewrite `README.md` in plain language —
  1. **The problem:** why a naive RAG is dangerous on financial filings (look-ahead,
     restatements, fiscal calendars, LLM arithmetic, meaningless metrics).
  2. **Architecture diagram:** the two lanes (numbers → SQL; text → chunks → hybrid
     search) → router → generation → fact-checker.
  3. **Results table** from the frozen golden bank: fused vs dense vs sparse recall@10,
     quant exact-match, typed-abstention rate, look-ahead leaks, router accuracy.
  4. **Key design choices** and the reason for each, linking into the ADRs (`docs/production/adr/`).
  5. **How to run** (compose, keys, backfill, gates) + what's next (this roadmap).
  Internal codes stay in the deeper docs, glossed if they appear at all.
- **Exit:** README reviewed by the user; every number in it traceable to a gate or eval
  run on the frozen bank.

### L1 — Observability, cost and answer grading *(build this first)*
- **Goal:** see inside your own pipeline, and learn to evaluate a RAG on cost and on the
  quality of its written answers, not just on retrieval.
- **Build — tracing + cost:** instrument `answer()` to emit a trace per query — route +
  confidence, retrieval scores, SQL template + params, verifier verdict, **tokens, latency
  per stage, and a cost estimate**. A small CLI to run the golden bank and roll up
  per-stage cost + quality. No web API.
  - *Trace contract (from original phase 6):* one JSON line per question — question,
    as_of, router decision + confidence + reason, retrieval sets with dense/sparse/RRF
    scores, SQL template + bound parameters, executor results + citations, verifier
    verdicts, model + tokens in/out, latency per stage, cost. **Any eval failure must be
    reproducible from its trace alone.**
  - *Not taken from phase 6:* the API, the answer cache, and the budget alarm (cost is
    ~0 here; the report shows cost instead).
- **Build — answer grading (LLM-as-judge):** today numbers are checked strictly by the
  verifier, but nothing grades the *text* of narrative answers — the M0 gate runs
  model-free. Add a judge that, for each narrative-route golden question:
  1. **Faithfulness:** splits the generated answer into claims and marks each as supported
     or not by the retrieved chunks → a per-answer faithfulness score.
  2. **Relevance:** does the answer address the question that was asked?
  Rules: the judge never grades numbers (the verifier owns those); ideally a **different
  model** from the one that wrote the answer (a model grading its own output is lenient) —
  record which model judged; verdicts and judge token cost go into the trace and L1's
  cost report. The judge makes live model calls, so it runs in the report CLI, **not** in
  the gates (CI stays fixtures-only).
- **Calibrate the judge:** **[HUMAN]** grades ~20 generated answers by hand (supported /
  not supported, answers the question / doesn't) in `golden/judge_calibration_v0.yaml`
  (~1 hr). Report the judge's agreement with the human labels. The judge's scores are
  quoted only once that agreement is recorded; if it's poor, fix the judge prompt first.
- **Learning payoff:** the transferable skill — "evaluate any RAG on performance *and*
  cost," including the standard interview question *"how do you measure hallucination?"*
  — and the habit of testing the grader before trusting it.
- **Honest note:** in this project the dollar cost is ~0 (free-tier Gemini + local models),
  so the interesting axis is **latency / compute budget** and the **methodology**. The
  method is identical when the costs are real. Free-tier rate limits may make a full
  golden-bank judge run slow; that's a cost finding too.
- **Exit:** a trace file per query; a report showing retrieval quality, answer faithfulness
  + relevance, and cost/latency per stage over the golden bank; judge–human agreement
  recorded; README results table updated.

### Showcase 2 — Demo page + video (~3 days)
- **Goal:** a reviewer sees the system working without installing Postgres, downloading
  SEC filings or embedding 7,033 chunks.
- **Why after L1:** the trace is the most distinctive thing to show — it makes the "how"
  visible, not just the answer.
- **Build:** a single local page (e.g. Streamlit) that calls `answer()` directly: a
  question box + optional as-of date → the answer, its citations (linked to the SEC
  filing), and an expandable trace (route, retrieved chunks with scores, SQL template,
  verifier verdict, time per stage). Include preset example questions that show each
  behaviour: a number with its source, a text answer, a point-in-time question, a JPM
  abstention, a clarifying question, an out-of-scope refusal. **Not hosted** — hosting
  the database and models is the cost trap; the video is what reviewers watch.
- **Video:** a ~2-minute screen recording walking through the preset questions, embedded
  or linked at the top of the README, plus 2–3 screenshots.
- **Exit:** page runs locally against the real corpus; video + screenshots in the README.
  Re-recorded after L5.

### L2 — Chunking evaluation
- **Goal:** learn how chunking choices change what search can find, and measure it at the
  level of the actual answer text — not just "right section."
- **Why it's needed:** today's retrieval eval grades at **(filing, section)** level — the
  harness collapses every returned chunk to its `(accession, section)` key before scoring.
  Any chunk from the right section counts as a hit, even one that doesn't contain the
  answer. So it can't show whether the answer text was retrieved, can't see answers split
  across two chunks, and can compare chunking strategies only coarsely. The current
  parameters (~800 tokens, ~100 overlap — design §4.5) were set in the design and never
  measured; real chunks run up to 1,634 tokens because the chunker's token count is an
  estimate (ADR-0011).
- **Build:**
  1. **Quote-level answer key** — `golden/snippets_v0.yaml`: for each of the 26
     retrieval-scored questions in `factual_v0`, one or more short exact quotes (about a
     sentence) from the gold section that answer it. Drafted by the agent, **[HUMAN]
     confirms each quote** (~1 hr). Additive: the frozen section-level bank is untouched.
     Frozen before any chunking variant is scored.
  2. **Chunk-level metrics** in `eval/`: **answer-hit@k** (share of gold quotes found
     inside at least one top-k chunk, whitespace/case-normalized) and **split answers**
     (gold quotes that no single chunk contains in full).
  3. **Measure first:** re-count the current chunks with the real bge-m3 tokenizer.
  4. **Variants, side by side** (the live `chunks` index and frozen baselines are not
     touched): current ~800/100 · smaller ~400/50 · larger ~1,200/150 · no overlap ~800/0.
     Each is chunked, embedded and searched separately.
- **Learning payoff:** the core chunking trade-off — small chunks match precisely but lose
  context and split answers; large chunks keep context but blur the match and send more
  tokens to the model; overlap reduces split answers at the cost of more chunks.
- **Exit:** one table — variant × section recall@10 · answer-hit@10 · split answers ·
  chunk count · avg tokens sent to generation · embedding time (L1's tooling) — and a
  written keep/change decision as a new ADR. If the chunking changes: re-embed the live
  index, then re-record baselines on it before L3. A change that lowers any frozen
  baseline needs its own ADR (baselines otherwise only ratchet up). README
  results table updated.

### L3 — Reranker (advanced retrieval)
- **Goal:** learn the "slow-but-smart second pass" and how to justify it with numbers.
- **Build:** a cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) over the fused top-20 →
  top-8, behind the existing retrieval interface (a config flag, so it's A/B-able).
  Measured on the chunking L2 settles on.
- **Learning payoff:** measure its **lift** on the frozen golden bank at **both** levels —
  nDCG@8 / recall (section) and answer-hit@8 (quote; catches a better chunk moved up
  *within* a section, which section-level scores can't see) — plus answer faithfulness
  (L1's judge) — **and its cost** (+ latency per query, via L1's tooling) — then decide if
  it's worth it. That decision *is* the skill.
- **Exit:** reranker on/off comparison on the golden bank: quality delta (both levels +
  faithfulness) and latency delta, with a written go/no-go. README results table updated.
- *From original phase 8:* the gate records the nDCG lift as a threshold that then only
  ratchets up. Conversation memory and conflict surfacing (the rest of phase 8) stay cut.

### L4 — GraphRAG POC
- **Goal:** answer a **relational** question that hybrid + SQL structurally cannot.
- **Build (POC scope, not production):** a small entity/edge graph — a handful of real,
  provenance-carrying relationships (e.g. WMT–COST peers, CAT–DE peers, NVDA→hyperscaler
  exposure), seeded/extracted from the filings with the source snippet on each edge. A
  simple traversal that returns the subgraph + evidence.
- **Learning payoff:** *why and when* a graph earns its place; the meta-skill of proving a
  technique is (or isn't) needed on your data.
- **Exit:** one golden "exposure/peer" question answered with edge provenance in the
  citation — something M0 correctly refuses today. README results table updated.
- *From original phase 10:* **decision gate first** — run the 4 graph golden questions
  (F29–F32) through the system; build only for the ones hybrid + SQL genuinely can't
  answer, and write a no-build ADR if none. Rules: the graph stores **no numbers** (any
  metric leg goes through the numbers engine); non-graph golden questions must not regress.
  Neo4j is optional at POC scale — Postgres tables are acceptable.

### L5 — Monitoring POC
- **Goal:** the proactive mode + event-driven design + alert quality.
- **Build (POC scope):** a watchlist + a monitor over the **daily filings feed we already
  have** (material 8-Ks by item code), with dedup and cited alerts. **Real-time market data
  is deferred** (licensed/expensive — the cost trap; EOD/filings only).
- **Learning payoff:** event-driven systems, deduplication, and alert **precision/recall**
  (a monitor that cries wolf is worse than none).
- **Exit:** a watchlist produces material, non-duplicate, cited alerts from fixture events,
  scored for precision/recall. README results table updated; demo video re-recorded.
- *From original phase 12:* events come from 8-K **item codes** (2.02 results, 5.02
  officer changes, 1.01 material agreements, 8.01 other); alerts are **exactly-once per
  accession**; alert text passes the verifier (cited, no invented numbers); tested on a
  synthetic 8-K fixture stream (gates stay offline). News monitors stay cut.

## Effort & the honest caveats

- **Rough total: ~8–10 weeks** at a learning pace (vs. ~4–5 months for the full product) —
  because the calendar-burning parts (real-time data, fine-tuning, full hardening) are cut.
  L2 adds roughly a week (re-embedding 7,033 chunks per variant is its slow step); the
  answer grading, README and demo page add roughly another week between them.
- **In hours of the human's time** (Claude builds; the human verifies, grades, decides, and
  does the exercises): roughly **55–70 h** for all eight steps — sign-off 8–12, README 1–2,
  L1 6–8, demo 3–4, L2 6–8, L3 4–6, L4 6–8, L5 5–7, plus 20–30% for things breaking. The
  sign-off is the honest test of this estimate: after the first 20 checklist items,
  multiply the per-item rate by 8.
- **If time is short (~30–40 h):** do sign-off → README → L1 → demo, then **L3 (reranker)**
  with chunking left as-is; L2, L4 and L5 become later work (~15–20 h more). Trade-off: if
  chunking is changed afterwards, the reranker numbers must be re-measured.
- **Eval integrity is the one hard dependency:** freeze/verify the golden bank (the M0
  verification) before quoting any chunking/reranker/graph "lift" as a result — in the
  README or anywhere else.
- **Cross-cutting learning goal — "evaluate any RAG":** retrieval and number eval already
  exist (recall@10, MRR, nDCG, exact-match, look-ahead, Phase 3); L1 adds the
  **cost/latency** half and **answer faithfulness**; L2 adds the **quote-level** half; L3
  is the case study that joins them.

## Relationship to the committed record

- Supersedes ADR-0009 (which committed to stopping at M0); amended by ADR-0016 (adds L2,
  renumbers reranker/graph/monitoring to L3–L5) and ADR-0017 (adds answer grading to L1, and the
  Showcase 1 README and Showcase 2 demo page).
- Uses subsets of phases 6, 8, 10, 12, plus the new L2 and the Showcase steps; **does not**
  build the API (phase 6 remainder), sources v2 / conversation / conflicts (phase 7 / part
  of 8), fine-tune (phase 9), multi-hop agentic (phase 11), or full hardening (phase 13).
- The archived design (`archive/design_us.md`) keeps the original intent for each subset;
  `docs/production/` describes what is actually built.

## Definition of done — every step

A step is done when all of these are true:

1. **Gate:** its own `gates/<step>.py` passes, wired into `make gate`, and every earlier
   gate still passes.
2. **Plan:** `docs/implementation/current/<step>.md` held the plan while building; on
   completion it moves to `docs/implementation/completed/`.
3. **Production docs:** the LLD for every component it touched is updated (new component →
   new LLD); HLD §8 updated if it changes a design difference.
4. **Decisions:** any deviation or choice is an ADR.
5. **Learning:** the matching `docs/learning_docs/` section is written (brief before
   building, finished after) with its check-yourself questions.
6. **Status:** `docs/implementation/status.md` updated; README results table updated
   (from Showcase 1 on).
