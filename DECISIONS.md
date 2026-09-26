# DECISIONS

Deviations from pins (U1–U13), threshold changes, and scope changes land here, dated,
with what/why/what-it-supersedes. Silent deviations are defects.

---

## 2026-07-10 — #1: US market build; india_rag independent

This repo builds the US-market system as a fully standalone project
(docs v0.3). The sibling `india_rag/` project is independent; its documents are
never an authority here. Supersedes the earlier delta-plan document structure.

## 2026-07-10 — #2: pgvector via `pgvector/pgvector:pg16` image

Pin U12 says "postgres:16 + pgvector". Stock `postgres:16` does not ship the
extension; the official `pgvector/pgvector:pg16` image is postgres:16 with the
extension compiled in. Chosen over building a custom image. Extension enabled at
initdb via `db/init/01_extensions.sql` locally; CI provisions the same extension
with an explicit `psql` step because service containers don't mount the repo.

## 2026-07-10 — #3: `universe.json` is derived, never hand-edited

`universe.json` (repo root, for [HUMAN] approval visibility) is generated from
`fixtures/company_tickers.json` + the pinned constants in `src/us_rag/universe.py`
by `scripts/build_universe.py`. The Phase 0 gate re-derives it byte-for-byte, so
hand edits fail CI by construction. Design §1.2's CIK column is a hint only; the
SEC snapshot wins on mismatch — except where `CIK_OVERRIDES` pins a filing entity
deliberately (see #4).

## 2026-07-10 — #4: XOM CIK override — holding-company reorganization (2026-07-01)

The live `company_tickers.json` maps XOM → CIK 0002115436 ("ExxonMobil Holdings
Corp"), a successor registrant whose first EDGAR filing is an 8-K12B dated
2026-07-01 and which has **no 10-K/10-Q filings**. All FY2024/FY2025 corpus
filings live under the predecessor, Exxon Mobil Corp, CIK 0000034088 (verified
via both entities' submissions JSON on 2026-07-10; predecessor still filing as
of 2026-07-06). `CIK_OVERRIDES` in `src/us_rag/universe.py` pins XOM to the
predecessor CIK with a `cik_note` in universe.json. Phase 2's backfill and the
Phase 1 security master must treat ticker→CIK as point-in-time (design §4.3) —
this event is the in-corpus proof of why. Revisit when ingesting anything the
successor entity files.

## 2026-07-12 — #6: working mode — "I build, you consolidate" learning loop

The project's goals are the product AND the human learning the domain, weighted
equally. Agreed loop: plain-language brief (learn/phase_NN_brief.md) BEFORE each
phase; plain walkthrough + one rebuild-it-yourself exercise (learn/phase_NN.md)
AFTER its gate is green; learn/glossary.md defines every term; no unexplained
jargon in learn/. Retroactive coverage for Phases 0–1 written 2026-07-12.

## 2026-07-17 — #7: STATUS.md + CURRENT_PHASE.md as maintained entry points

Two root files are maintained from now on (extends #6). **STATUS.md** — the
global state file: project target, phase map, current phase, done/blocked —
the first read for any AI or human picking up the repo; updated at phase
transitions and whenever blockers change. **CURRENT_PHASE.md** — the active
phase's pre-build deep dive (theory → code, complete pipeline flow, learning-
first plain language). It supersedes the thin `learn/phase_NN_brief.md` format
at greater depth: written BEFORE building each phase; on gate-green it is
archived as `learn/phase_NN_brief.md` and rewritten for the next phase.
Neither file is a design authority — execution plan and design doc still win.

## 2026-07-19 — #8: zero-cost LLM policy — Gemini free tier replaces Anthropic API

The design docs name the Anthropic API for LLM call sites (U13 extraction now;
generation from Phase 5). At the user's request the project runs at zero API
cost: `headline.py` now calls the Gemini API (`google-genai`, `GEMINI_API_KEY`,
free tier — 10 req/min, 1,500 req/day, ample for ~117 one-time calls plus
pacing/429 retry). Why this is safe for U13 specifically: extraction quality is
not load-bearing — the fail-closed normalizer and 100% human verification catch
any model's mistakes, so provider choice only moved cost, not risk. Inputs are
public SEC filings, so the free tier's data-use terms are a non-issue. Policy
forward: future LLM call sites (Phase 5 generation, Phase 7 headline v2) default
to the free tier; revisit per phase if a gate shows quality is insufficient.
Deviation from design_us.md provider naming; supersedes the `ANTHROPIC_*` env
keys (`.env.example` updated).

**Amended 2026-07-19:** the quota assumption above was stale. Observed live:
the free tier allows only **20 requests/day** for `gemini-2.5-flash`
(429 RESOURCE_EXHAUSTED, quotaId `GenerateRequestsPerDayPerProjectPerModel-
FreeTier`, quotaValue 20) — not 1,500/day. `GEMINI_MODEL` switched to
`gemini-2.5-flash-lite`, which has a separate and larger per-day free quota.
Safe for the same reason as the original decision: U13 extraction quality is
not load-bearing (fail-closed normalizer + 100% human verification). If
flash-lite's daily quota also runs out mid-backfill, the extract command is
resumable — rerun it the next day; staged rows are never lost.

## 2026-07-19 — #9: target scope pinned to M0 (phases 0–5); 6–9 polish; 10–13 shelved

User decision (2026-07-19): the committed build target is **M0 — the end of
Phase 5** (end-to-end question answering with the M0 gate: quant exact-match
≥ 90%, 100% typed abstention on unanswerables, zero look-ahead violations,
every number cited). Phases 6–9 are **polish**: reassessed after M0 ships,
built only if the user opts in then. Phases 10–13 (M2–M5) are shelved; the
4 graph goldens in the Phase 3 bank keep their expected-typed-refusal status
indefinitely unless M2 is revived. The execution plan and design doc remain
the authorities on HOW each in-scope phase is built — this entry narrows only
WHICH phases are committed.

## 2026-07-19 — #10: Phase 1 gate quarter-duration band widened 85–98 → 83–111 days

The "plausible durations" check (gates/phase_01.py, check_fiscal_seed_sanity)
assumed all quarters are 13–14 weeks. COST's real calendar is 12-week quarters
with a 16-week Q4 — measured as `period_end - period_start` those are 83 and
111 days — so the 8 XBRL-derived COST quarter rows (FY2024–25 Q1–Q3 at 83d,
Q4 at 111d, all verified correct against period contexts) failed a correct-data
check. Band widened to 83–111 days; the FY band (360–372) is untouched. A
tighter exact-membership check (83/90/97/111) was rejected: calendar-quarter
companies (e.g. JPM, XOM) legitimately measure 89–91 days.

## 2026-07-11 — #5: "append-only" = write-once `superseded_by`, trigger-enforced

U11 says facts are append-only, but the supersession *link* lives on the old row
(`superseded_by`, per design §4.2 DDL) — setting it is technically an UPDATE.
Interpretation pinned here: the `facts_append_only` trigger forbids DELETE always
and permits exactly one mutation per row — setting `superseded_by` from NULL once,
with every other column bit-identical. TRUNCATE bypasses row triggers, so the
Phase 1 gate lints it out of `src/` instead (tests may use it; they run on a
disposable DB). Consequence for Phase 2/U13: rows are inserted only *after* human
verification (`human_verified=true` at insert) — there is no post-insert flag
flip, because the trigger would forbid it.

## 2026-07-31 — #11: embedding backfill memory-bounded for 8 GB Apple Silicon

`narrative.embed_missing` OOM'd mid-run on the target machine (Apple M2, 8 GB),
stalling after ~320 of 7,033 chunks. Root cause: sentence-transformers defaults
to the M-series GPU (MPS), whose memory is the same 8 GB the display and apps
use; a 32–64-wide batch of long chunks exhausted it. Fix (no design impact — this
is a runtime knob, not a pin change): default `device="cpu"` (regular, pageable
RAM), `batch_size=8`, and `max_seq_length=2048`. The cap was chosen from data,
not a chars/token guess — tokenized all 7,033 chunks: max 1,634 tokens, p99 1,307,
so a 2,048 cap truncates **zero** chunks (a 1,024 cap would have silently
truncated 503 / 7.15% — rejected). All three are env-overridable
(`US_RAG_EMBED_DEVICE` / `_BATCH` / `_MAXLEN`); set `US_RAG_EMBED_DEVICE=mps` to
trade the safety margin for speed once other apps are closed. CPU is slower but
predictable, which is the right default for the constrained laptop.

## 2026-07-31 — #12: Phase 3 started with the Phase 2 gate at 5/9 (human items deferred)

User decision (2026-07-31): begin Phase 3 (eval harness + hybrid retrieval) before
Phase 2's gate is fully green. Phase 2's 5 mechanical checks pass; the 4 red checks
are all [HUMAN]/[KEY] — spot-checks (gate 2), prices/Tiingo (gate 5), U13 row
verification (gate 7), supersession countersign (gate 9) — and none of them block
Phase 3 engineering. Rationale: the corpus is fully built and **embedded (7,033/7,033
as of today)**, so retrieval and evaluation can be built and *measured on real data*
now, while the last-mile Phase 2 items trail. Guardrails, so this stays honest:
- The golden bank's **quant** gold values stay coupled to the spot-checks (execution
  plan) — quant exact-match numbers are **provisional** until `spot_checks.json` lands.
- `make gates` will show `phase_02` red until the human items are done — **expected,
  not a regression**; `phase_00`/`phase_01` remain green.
- **Do not tune retrieval until the golden bank is frozen** (execution plan).
- Pre-build brief written as `learn/phase_03_brief.md`. `CURRENT_PHASE.md` still holds
  the Phase 2 deep-dive; it is archived to `learn/phase_02_brief.md` and rewritten for
  Phase 3 when `phase_02` goes green (per #7) — not clobbered mid-phase.

## 2026-08-04 — #13: segment-SQL deferred; segment questions use the narrative path for M0

User decision (2026-08-04): defer segment dimensional-XBRL ingestion. Phase 2 loaded
company-level facts from SEC `companyfacts`, which carries no segment dimensions; loading
segment facts needs a new dimensional-iXBRL extraction pass over the blobs (substantial,
error-prone, needs human spot-checks). The `segment_value` executor is built and fails
safe (abstains `no_segment_data`) until data lands. For M0 the 8 golden segment questions
are answered by the **Phase 3 narrative path** (gold = Item 7 MD&A), already
retrieval-scored — so segment questions remain answerable. The Phase 4 gate's segment
check is relaxed accordingly: segment questions are evaluated as narrative retrieval, not
SQL exact-match, until segment-SQL is revived post-M0. Design §6.2 segment facts / U10
remains the eventual target; this narrows only WHEN it is built (after M0).

## 2026-08-06 — #14: M0 router is rule-based (deterministic), not an LLM classifier

Design §6.0 specifies "an LLM classifier" for the router. For M0 the router is built
**deterministically** (entity + fiscal resolution first, then keyword/pattern rules →
typed route + confidence). Why: it is auditable and unit-testable, it removes an LLM
call (and its latency/flakiness/quota) from the single most safety-critical decision, and
it can **structurally** prevent the one dangerous misroute (a numeric question going to
text-only — design §6.1). The router is measured on the 60-question golden bank (the
design's router confusion matrix) and the misroute rate is recorded as the M0 baseline.
An LLM classifier remains the drop-in upgrade behind the same typed interface if the
measured accuracy proves insufficient. Deviation from design §6.0 provider naming only;
routing contract (the typed routes) is unchanged.

## 2026-08-13 — #15: post-M0 scope is a learning-optimized selection (supersedes #9)

User decision (2026-08-13): after M0 ships, pursue a **learning-focused** roadmap rather
than product completeness — full spec in `docs/roadmap_learning.md`. Committed post-M0
work, in order: **L1 observability + cost eval** (phase 6 minus the API), **L2 reranker**
(phase 8's reranker only), **L3 GraphRAG POC** (phase 10, POC scope), **L4 monitoring POC**
(phase 12, POC scope). Target skill: build a RAG from ingestion → hybrid retrieval →
reranking → GraphRAG, instrument it (observability), and evaluate any RAG on performance
**and** cost. **Deliberately cut** (low RAG-learning value or cost/infra traps): the web
API (phase 6 remainder), embedder fine-tuning (phase 9), sources v2 / conversation /
conflict-surfacing (phase 7 / part of 8), multi-hop agentic (phase 11), real-time market
data, and full hardening (phase 13). Rationale: the two dropped headliners are generic web
engineering and a specialized ML side-quest — neither teaches transferable RAG skill.
Supersedes #9 (stop-at-M0). M0 verification is still the gate to freeze the golden bank so
reranker/graph "lift" numbers are trustworthy. Execution plan + design doc remain the HOW
authorities for each subset.

## 2026-09-17 — #16: chunking evaluation added as L2 (amends #15)

User decision (2026-09-17): add a chunking evaluation to the post-M0 roadmap, after
observability (L1) and before the reranker. Why: the retrieval eval grades at (filing,
section) level — `eval/harness.py` collapses returned chunks to `(accession, section)` keys
before scoring — so any chunk from the right section counts as a hit. It cannot tell
whether the answer text was retrieved, cannot see answers split across chunks, and compares
chunking strategies only coarsely. The chunk parameters (~800 tokens / ~100 overlap, design
§4.5) were set in the design and never measured; real chunks run up to 1,634 tokens (#11).
The same blind spot would hide part of a reranker's lift (a better chunk moved up within one
section doesn't change the score). New L2 adds a quote-level answer key
(`golden/snippets_v0.yaml`, additive — the frozen section-level bank is untouched), chunk-level
metrics (answer-hit@k, split answers), and a side-by-side chunk-size experiment; the reranker
is then measured at both levels. Renumbering: reranker L2→L3, GraphRAG L3→L4, monitoring
L4→L5. Spec: `docs/roadmap_learning.md`. Design §4.5 parameters stand unless L2's written
decision changes them.

## 2026-09-17 — #17: answer grading added to L1; README and demo page added as Showcase steps (amends #15)

User decision (2026-09-17): the project should also read well as a portfolio piece for a
~1-year-experience candidate. Three gaps were identified and added to
`docs/roadmap_learning.md`:
- **Answer grading (in L1).** The verifier checks numbers strictly, but nothing grades the
  *text* of narrative answers — the M0 gate is model-free and design §10.1 has no
  answer-text metric. L1 adds an LLM judge (faithfulness: each claim supported by the
  retrieved chunks; relevance: answers the question), calibrated against ~20 hand-graded
  answers ([HUMAN], `golden/judge_calibration_v0.yaml`) before its scores are quoted. The
  judge never grades numbers, ideally uses a different model from the generator, and runs
  in the report CLI only — gates stay fixtures-only.
- **Showcase 1 — README**, right after M0 sign-off (first real numbers): problem,
  architecture diagram, results from the frozen bank, design choices, how to run. Every
  later L updates its results table.
- **Showcase 2 — demo page + ~2-minute video**, right after L1 (so the trace can be shown):
  a single local page calling `answer()` directly, not hosted. This does **not** revive
  phase 6's web API, which stays cut per #15 (no endpoints, cache, auth or hosting).
Considered and not added: an agent/tool-calling POC (phase 11 stays cut). Estimate moves
from ~7–9 to ~8–10 weeks.

## 2026-09-17 — #18: doc set consolidated; START_HERE.md is the entry point (amends #7)

User decision (2026-09-17): remove docs that were stale or duplicated, and write one
document that explains how to read the rest and how the project will be finished.

**Removed** (all recoverable from git history):
- `CURRENT_PHASE.md` — held the Phase 2 deep dive; never archived when Phase 2 went green
  and stale ever since (Phase 5 is done). The learn/ walkthrough for Phase 2 covers it.
- `phases_docs/` (phase_00, phase_01) — the engineer-to-engineer writeup convention was
  abandoned after Phase 1; phases 2–5 never got one, and the files claimed "every phase
  gets one of these". `learn/phase_0N.md` + the code + gates carry the same ground.
- `docs/random.txt` — a one-line-per-phase summary of the 14-phase plan; duplicated the
  execution plan and described phases now cut.
- `learn/phase_03_brief.md`, `phase_04_brief.md`, `phase_05_brief.md` — the "before" docs
  for steps whose walkthroughs exist; only 3 of 6 phases had one, so the folder was
  inconsistent.

**Added:** `START_HERE.md` — what the project is, which doc to read when, the authority
order, the current state, the working loop, the eight remaining steps, the hard rules, the
commands, and where new files go.

**Protocol change (amends #7):** `CURRENT_PHASE.md` is gone. The active step's plain-language
brief lives at `learn/<step>_brief.md`; when the step's gate is green the brief is folded
into `learn/<step>.md` and deleted, so `learn/` keeps one file per step. `STATUS.md` remains
the state file; `START_HERE.md` is the entry point for humans and AI sessions alike.
`CLAUDE.md`, `STATUS.md`, `README.md` and `learn/README.md` updated to match.
