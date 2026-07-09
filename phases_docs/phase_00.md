# Phase 0 — Scaffold, Services, CI, Protocol

**Status:** ✅ gate green (`make gate PHASE=0`, 5/5 checks) · 2026-07-10
**Implements:** `docs/execution_plan_us.md` Phase 0 · design §1.2 (universe), §3.1 (fair access), §4.1 (infra)
**Decisions logged this phase:** DECISIONS.md #1–#4

This document explains *what* was built, *why each piece exists*, and the theory
behind the choices — at code level and concept level. Every phase gets one of these.

---

## 1. What Phase 0 is for (theory)

Phase 0 builds no product features. It builds the **rails that make every later
phase honest**:

- **Gates are executable definitions of done.** Each phase ships a plain script
  (`gates/phase_NN.py`) whose exit code *is* the phase's completion status. This is
  TDD at phase granularity: the gate is written from the plan's gate spec, and the
  phase is "done" when — and only when — the script passes. No judgment calls, no
  "mostly working."
- **The regression rule.** `make gates` (→ `gates/run_all.py`) runs *every* existing
  gate in order and stops on the first failure. Completing Phase 3 never excuses
  breaking Phase 1. CI runs this on every push, so regressions are structurally
  visible, not anecdotally noticed.
- **Fixtures-only CI.** Gates never call external data APIs (SEC, Tiingo,
  Anthropic). Everything a gate checks must be derivable from committed files plus
  local services. This makes CI deterministic (no flakes from rate limits or
  upstream changes) and honest (a green build means *our* code is right, not that
  the internet was up). The one nuance: gates *do* talk to the local postgres —
  that's infrastructure, not data fetching. The rule is about data provenance, not
  about sockets.
- **Decisions are written down or they didn't happen.** `DECISIONS.md` is the
  append-only log of every deviation from the pinned decisions (U1–U13), every
  threshold change, every scope cut. The protocol exists because a solo/agentic
  project's failure mode is silent drift — a plan that says one thing and a repo
  that quietly does another.

Why scaffold *before* any product code? Because the first real phase (Phase 1's
bitemporal schemas) needs a database to migrate, a gate to prove itself against,
and a CI loop to keep it proven. Building rails after the train is running is how
projects accumulate untested corners.

---

## 2. What exists now

```
US_rag/
├── CLAUDE.md                  # working agreement + hard rules (authority order)
├── DECISIONS.md               # decision log, entries #1–#4
├── Makefile                   # up/down/sync/gate/gates/verify-live
├── README.md                  # quick start
├── docker-compose.yml         # pgvector/pgvector:pg16, host port 5433
├── pyproject.toml             # uv-managed; deps: psycopg, httpx (that's all, deliberately)
├── uv.lock                    # committed — reproducible env
├── .python-version            # 3.12
├── .env.example               # template incl. SEC_EDGAR_USER_AGENT contract
├── .env                       # local only, gitignored (real UA; keys pending [HUMAN])
├── universe.json              # DERIVED — the 10 pinned companies with CIKs
├── db/init/01_extensions.sql  # CREATE EXTENSION vector at first initdb
├── docs/                      # design_us.md, execution_plan_us.md (v0.3, standalone)
├── fixtures/
│   └── company_tickers.json   # committed SEC snapshot (10,418 entries, fetched 2026-07-10)
├── gates/
│   ├── common.py              # tiny gate runner (checks → PASS/FAIL → exit code)
│   ├── phase_00.py            # this phase's 5 checks
│   └── run_all.py             # regression runner
├── phases_docs/               # these writeups
├── scripts/
│   ├── build_universe.py      # snapshot → universe.json (offline, deterministic)
│   └── verify_live.py         # [HUMAN] one-time live SEC cross-check
├── src/us_rag/
│   ├── env.py                 # 20-line .env loader (no dotenv dependency)
│   ├── universe.py            # PINNED_UNIVERSE + CIK_OVERRIDES + build_universe()
│   └── {ingest,store,query,serve}/   # empty packages — Phase 1+ fills them
└── .github/workflows/ci.yml   # postgres service + uv + run_all on every push
```

---

## 3. File-by-file: what and why

### `pyproject.toml`, `uv.lock`, `.python-version`
- **uv** manages the environment; `uv sync` gives an identical env locally and in CI,
  and `uv run` guarantees gates execute inside it. The lockfile is committed —
  "works on my machine" is a class of bug we opt out of on day one.
- **Dependencies are two:** `psycopg[binary]` (the gate's DB check) and `httpx`
  (`verify_live.py` only). Nothing speculative — each phase adds its own deps when
  its gate demands them. `src/us_rag` is installed editable via hatchling, so gates
  and scripts do `from us_rag.universe import ...` with no path hacks (the small
  `sys.path.insert` shims in `gates/common.py` and `scripts/` keep raw
  `python3 gates/phase_00.py` working even outside uv).

### `docker-compose.yml` + `db/init/01_extensions.sql`
- **Image `pgvector/pgvector:pg16`** — pin U12 says "postgres:16 + pgvector"; stock
  `postgres:16` doesn't ship the extension, and the official pgvector image *is*
  postgres:16 with it compiled in (DECISIONS.md #2). One database will hold facts,
  chunks, embeddings (pgvector), and FTS — one moving part until a pivot says
  otherwise (P-US-8).
- **`db/init/` mounts into `/docker-entrypoint-initdb.d`** — postgres runs any SQL
  there exactly once, at first initdb of the volume. That's where
  `CREATE EXTENSION vector` lives, so a fresh `make up` produces a ready database
  with no manual step.
- **Host port 5433, container 5432.** A real lesson from this machine: a
  pre-existing local postgres owns `127.0.0.1:5432`, and macOS resolves `localhost`
  to that listener *ahead of* Docker's `0.0.0.0` proxy. The symptom was surreal —
  the container healthy, yet the gate greeted by `role "usrag" does not exist`,
  because psycopg was talking to a *different postgres than docker was running*.
  Diagnosis: `lsof -nP -iTCP:5432 -sTCP:LISTEN` showed both listeners. Moral: when
  a healthy service gives inconsistent answers, confirm *which* service you're
  actually talking to. The healthcheck runs inside the container and can never see
  this class of problem.
- **`--wait` in `make up`** blocks until the healthcheck passes, so `make up &&
  make gate PHASE=0` can't race the database's startup.

### `Makefile`
Five verbs, no cleverness: `up`/`down` (compose), `sync` (uv), `gate PHASE=N`
(zero-pads N and runs that gate), `gates` (regression runner), `verify-live`
(the [HUMAN] cross-check). The Makefile is the whole operational interface — CI
and CLAUDE.md both speak in these verbs.

### `.env.example` / `.env`
- `.env` is gitignored; `.env.example` documents the contract. The loader
  (`src/us_rag/env.py`) is 20 lines: parse `KEY=VALUE`, real environment wins over
  file values (so CI can inject `SEC_EDGAR_USER_AGENT` without a file). We skipped
  the `python-dotenv` dependency because those 20 lines are the whole requirement.
- **`SEC_EDGAR_USER_AGENT` is gate-checked to contain `@`.** EDGAR's fair-access
  policy requires a declared User-Agent with a contact email (design §3.1). Making
  the gate fail on a missing/anonymous UA turns a compliance rule into a build
  invariant — Phase 2's client physically can't ship without it.
- API keys (Anthropic, Tiingo) are *not* gate-checked at Phase 0 — nothing uses
  them yet. They become gate concerns at the phases that consume them (2 and 5).

### `CLAUDE.md`
The working agreement for any agentic session in this repo: authority order
(execution plan > design), the five hard rules (U8 no-formula-fiscal, U11
append-only supersession, no-LLM-arithmetic, rate-limiter untouchable,
fixtures-only CI), and the session protocol (read plan → implement to gate →
`make gate` → previous gates stay green → deviations to DECISIONS.md → stop at
`[HUMAN]`). It exists so process survives context resets.

### `fixtures/company_tickers.json` (the snapshot) and `universe.json` (derived)
- The snapshot is SEC's official ticker→CIK mapping (10,418 entries), fetched once
  at build time with the proper User-Agent and **committed**. Committing it makes
  universe resolution *reproducible and offline*: CI never fetches it, and a
  rebuild in five years produces the same bytes.
- `universe.json` is **never hand-edited** (DECISIONS.md #3). It's generated by
  `scripts/build_universe.py` from snapshot + the pinned constants in
  `src/us_rag/universe.py`, and gate check #4 *re-derives it and byte-compares*.
  A hand edit fails CI by construction. This is the cheapest possible version of a
  principle the whole system uses: **derived artifacts carry their derivation, and
  the derivation is the test.**
- Universe entries carry `fye_month_hint` and `week_52_53_calendar` as *hints for
  humans* — real fiscal boundaries come from `fiscal_calendars` populated from
  filings (pin U8). The hint field exists precisely so nobody is tempted to encode
  fiscal logic here.

### `src/us_rag/universe.py` — and why this logic lives in `src`, not `scripts`
The derivation is a pure function `build_universe(snapshot_path) -> str`. It lives
in the package so the *gate imports the same function the script runs* — one
implementation, verified byte-for-byte, importable by future phases (Phase 1's
security-master seed will read the same constants). `scripts/build_universe.py` is
a 10-line CLI shell around it.

### `scripts/verify_live.py`
The **only** networked verification, run once by a human (`make verify-live`,
smoke-tested green 2026-07-10). Semantics matter here: it does *not* naively diff
CIKs; it re-derives the universe **from live SEC data through the same pinned
logic** (including overrides) and compares to the committed file. So it answers
the right question — "would our derivation still produce this universe today?" —
and stays silent about irrelevant churn elsewhere in the 10k-row file.

### `gates/` — plain python, not pytest
A gate is a checklist that prints PASS/FAIL per item and exits nonzero on any
failure. Plain scripts keep the contract primitive: *exit code is everything*;
CI needs no plugin, `make` needs no runner, and the output reads as documentation.
(`pytest` arrives in Phase 1 for unit tests — fixtures like the fiscal matrix are
a natural fit there; gates will *invoke* test suites where appropriate.)
`gates/common.py` runs all checks rather than stopping at the first failure — a
gate should report everything wrong at once.

### `.github/workflows/ci.yml`
Postgres (same pgvector image) as a **service container**, `uv sync`, then the
regression runner. Two asymmetries with local dev, both deliberate and commented:
- Service containers can't mount `db/init/`, so CI provisions the extension with
  an explicit `psql -c 'CREATE EXTENSION IF NOT EXISTS vector'` step. The *gate*
  stays a pure verifier either way — provisioning differs, verification doesn't.
- CI sets a placeholder `SEC_EDGAR_USER_AGENT` (with an `@`). The check proves the
  configuration *plumbing*; the real identity lives only in local `.env`.

---

## 4. The XOM event — Phase 0's best lesson

While resolving the universe, the derivation printed a warning: the live snapshot
maps **XOM → CIK 0002115436, "ExxonMobil Holdings Corp"** — not the design table's
0000034088. Investigation against EDGAR (both entities' `submissions.json`):

- The new CIK's **first filing ever is 2026-07-01**, and it's an **8-K12B** — the
  form a *successor issuer* files under Rule 12g-3 when a holding-company
  reorganization replaces the listed entity. It has **no 10-K or 10-Q filings**.
- The old CIK — Exxon Mobil Corp — holds **every filing in our corpus window**
  (FY2024 10-K filed 2025-02-19, FY2025 10-K filed 2026-02-18, all 10-Qs) and was
  still filing as of 2026-07-06.

So nine days before this phase ran, ExxonMobil restructured, and the "current"
ticker mapping began pointing at an entity that has never filed an annual report.
Blind "snapshot wins" would have sent Phase 2's backfill to an empty registrant —
and the Phase 2 gate (registry counts) would have failed mysteriously, three
phases from the cause.

**Resolution (DECISIONS.md #4):** `CIK_OVERRIDES` in `universe.py` pins XOM to the
predecessor CIK, with the reason embedded in code *and* surfaced as a `cik_note`
field in `universe.json`. The rule hierarchy is now: snapshot wins over the design
table; a **documented override** wins over the snapshot; nothing wins silently.

**Why this matters beyond XOM (theory):** ticker→CIK is itself a **point-in-time
mapping** — the exact phenomenon the design's security master models with validity
windows on tickers (design §4.3) and the whole system models with `knowledge_time`
(design §4.2). Phase 0 accidentally delivered a live specimen of the project's
central thesis: *identity and facts drift over time, and systems that store "the
current view" silently corrupt history.* Phase 1's security master and Phase 2's
backfill inherit a concrete requirement from this: XOM's filings resolve through
the predecessor CIK, and any future ingestion of successor-entity filings is a
DECISIONS.md event.

---

## 5. The gate, check by check

| # | Check | What a failure would mean |
|---|---|---|
| 1 | scaffold files present | repo layout drifted from plan §0.1 — protocol docs or rails deleted/moved |
| 2 | `SEC_EDGAR_USER_AGENT` has `@` | fair-access identity missing → Phase 2 client would violate SEC policy |
| 3 | postgres reachable + `pg_extension` row `vector` | stack down (`make up`), wrong port (the 5433 lesson), or init SQL didn't run — Phase 1 migrations would fail later and worse |
| 4 | `universe.json` byte-identical to derivation | hand edit, stale regeneration, or snapshot/constants drift — provenance of the corpus's *scope* is broken |
| 5 | 10 entries, CIKs zero-padded 10-digit | U1 violated or formatting broken (EDGAR URLs need the zero-padded form) |

Run: `make gate PHASE=0` · regression: `make gates` · both green 2026-07-10.

---

## 6. `[HUMAN]` checklist — remaining

- [ ] Create the remote repo and push (nothing here requires it yet; CI activates on first push).
- [ ] `ANTHROPIC_API_KEY` in `.env` — needed by Phase 2 (U13 extraction assist) and Phase 5.
- [ ] `TIINGO_API_KEY` in `.env` (free registration) — needed by Phase 2d.
- [x] `make verify-live` — run 2026-07-10: live derivation matches committed universe.
- [ ] **Approve the universe** — open `universe.json`, confirm the 10 names (note XOM's `cik_note`). This is pin U1's sign-off; Phase 2 backfills exactly these CIKs.

---

## 7. What Phase 1 consumes from Phase 0

- The running postgres+pgvector stack and `DATABASE_URL` convention → Phase 1's
  schema migrations and `AsOfContext`.
- `universe.json` + `us_rag.universe` constants → security-master seed rows
  (companies, tickers), including the XOM predecessor/successor situation as the
  first point-in-time ticker fixture.
- The gate rails + regression runner → `gates/phase_01.py` slots in with zero
  ceremony; pytest joins for the unit/fiscal fixture matrices.
- The env loader and the fair-access UA discipline → reused by everything that
  ever touches EDGAR.

**Next:** Phase 1 — data spine: schemas, the bitemporal `facts` table, unit
normalizer (fail-closed), fiscal resolver with the trap matrix (NVDA FY-labels,
53-week DE FY2025 candidate), and the U8 no-formula lint.
