# Architecture Decision Records

One file per decision: the context, what was decided, and what follows from it.
Numbers are permanent and match the old `DECISIONS.md` entries (so "DECISIONS #11" in
older notes is ADR-0011). New decisions get the next number; old ones are never edited
except to update **Status** when a later ADR supersedes or amends them.

**Types:** Architecture (how the system is built) · Data (facts about the source data) ·
Scope (what is and isn't built) · Process (how we work) · Operations (running it).

| ADR | Decision | Type | Status | Date |
|---|---|---|---|---|
| [ADR-0001](ADR-0001-us-build-standalone.md) | US market build is standalone; india_rag is independent | Scope | Accepted | 2026-07-10 |
| [ADR-0002](ADR-0002-pgvector-docker-image.md) | Use the `pgvector/pgvector:pg16` image for Postgres | Architecture | Accepted | 2026-07-10 |
| [ADR-0003](ADR-0003-universe-json-derived.md) | `universe.json` is derived, never hand-edited | Architecture | Accepted | 2026-07-10 |
| [ADR-0004](ADR-0004-xom-cik-override.md) | XOM pinned to the predecessor CIK after the 2026-07-01 reorganization | Data | Accepted | 2026-07-10 |
| [ADR-0005](ADR-0005-append-only-write-once-supersession.md) | "Append-only" means a write-once `superseded_by` link, enforced by a trigger | Architecture | Accepted | 2026-07-11 |
| [ADR-0006](ADR-0006-learning-loop.md) | Working mode: "I build, you consolidate" | Process | Accepted (layout amended by ADR-0018, ADR-0019) | 2026-07-12 |
| [ADR-0007](ADR-0007-status-file.md) | A maintained status file as the entry point for state | Process | Amended by ADR-0018 and ADR-0019 | 2026-07-17 |
| [ADR-0008](ADR-0008-gemini-free-tier.md) | Zero-cost LLM policy: Gemini free tier replaces the Anthropic API | Architecture | Accepted (amended same day) | 2026-07-19 |
| [ADR-0009](ADR-0009-scope-m0-only.md) | Target scope pinned to M0 (phases 0-5) | Scope | Superseded by ADR-0015 | 2026-07-19 |
| [ADR-0010](ADR-0010-quarter-duration-band.md) | Phase 1 quarter-length check widened from 85-98 to 83-111 days | Data | Accepted | 2026-07-19 |
| [ADR-0011](ADR-0011-embedding-memory-bounded.md) | Embedding backfill memory-bounded for an 8 GB laptop | Operations | Accepted | 2026-07-31 |
| [ADR-0012](ADR-0012-phase3-before-phase2-green.md) | Phase 3 started while Phase 2's human-only checks were still open | Process | Accepted | 2026-07-31 |
| [ADR-0013](ADR-0013-segment-sql-deferred.md) | Segment numbers via SQL deferred; segment questions use text search for M0 | Scope | Accepted | 2026-08-04 |
| [ADR-0014](ADR-0014-rule-based-router.md) | The M0 router is rule-based, not an LLM classifier | Architecture | Accepted | 2026-08-06 |
| [ADR-0015](ADR-0015-post-m0-learning-roadmap.md) | Post-M0 scope is a learning-optimised selection | Scope | Accepted (amended by ADR-0016, ADR-0017) | 2026-08-13 |
| [ADR-0016](ADR-0016-chunking-eval-l2.md) | Chunking evaluation added as L2 | Scope | Accepted | 2026-09-17 |
| [ADR-0017](ADR-0017-answer-grading-and-showcases.md) | Answer grading added to L1; README and demo page added as showcase steps | Scope | Accepted | 2026-09-17 |
| [ADR-0018](ADR-0018-doc-consolidation.md) | Doc set consolidated; START_HERE.md added | Process | Superseded by ADR-0019 (layout) | 2026-09-17 |
| [ADR-0019](ADR-0019-docs-three-sections.md) | Docs restructured into production, learning and implementation sections | Process | Accepted | 2026-09-26 |
| [ADR-0020](ADR-0020-corpus-selection-and-load-scope.md) | Corpus selection, facts load scope, and Q4 calendar closure (recorded retroactively) | Data | Accepted | 2026-09-26 |
| [ADR-0021](ADR-0021-engineering-track-and-ci.md) | Engineering track (E1–E3); branches, pull requests and a four-job CI | Process | Accepted | 2026-09-27 |
| [ADR-0022](ADR-0022-backend-frontend-layout.md) | Backend code under `backend/`; frontend design and future UI under `frontend/` | Architecture | Accepted | 2026-09-26 |


## Writing a new ADR

Copy any file, take the next number, fill in Context / Decision / Consequences, add a row
above, and update the Status line of any ADR it supersedes or amends.
