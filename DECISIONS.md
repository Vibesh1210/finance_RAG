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
