# 04 · Runbook

Everything runs locally on one laptop (developed on an 8 GB Apple M2).

Run all commands below from the repository root (`US_rag/`). Backend source and tools
live under `backend/`; frontend design lives under `frontend/docs/`. After pulling the
directory move, refresh the editable Python install with `uv sync --group embed`.

## 1. Prerequisites

- Docker Desktop (running), `uv`, Python 3.12 (uv installs it).
- A contact email for the SEC User-Agent.
- Optional keys: `GEMINI_API_KEY` (free, aistudio.google.com), `TIINGO_API_KEY` (free,
  tiingo.com).

## 2. First-time setup

```bash
cp .env.example .env          # set SEC_EDGAR_USER_AGENT="US-rag/0.1 (you@example.com)" and keys
make up                       # Postgres 16 + pgvector on localhost:5433
make sync                     # Python deps (dev group)
uv sync --group embed         # + sentence-transformers / bge-m3 (needed for search, gate 3, and pyyaml)
make migrate                  # apply backend/db/migrations/*.sql
make seed                     # companies, tickers, aliases, fiscal seeds
```

## 3. Loading data (order matters)

```bash
uv run python -m us_rag.ingest.backfill            # filings → blobs/ + documents   (EDGAR, ~8 req/s)
uv run python -m us_rag.ingest.facts_load          # XBRL → facts, fiscal_calendars, supersession links
uv run python -m us_rag.ingest.narrative --embed   # sections → chunks → bge-m3 vectors (CPU; slow, resumable)
make gate PHASE=4                                   # also (re)loads the metric registry from
                                                    # fixtures/metric_mappings.yaml (seed_metric_mappings)
# U13 press-release figures (human-gated):
uv run python -m us_rag.ingest.headline extract    # → fixtures/u13_staged.json (Gemini)
#   [HUMAN] verify every row, set "verified": true
uv run python -m us_rag.ingest.headline normalize
uv run python -m us_rag.ingest.headline insert     # refuses if any row is unverified
# Prices (needs TIINGO_API_KEY):
uv run python -m us_rag.ingest.prices
```

Every step is idempotent: re-running skips work already done (keyed by accession).
All support `--tickers AAPL MSFT` to limit scope.

## 4. Everyday commands

| Command | Does |
|---|---|
| `make up` / `make down` | start / stop the database |
| `make test` | unit tests (rebuilds `usrag_test`) |
| `make gate PHASE=N` | one phase gate |
| `make gates` | all gates in order; stops at the first red |
| `make verify-live` | one live call: compare the committed ticker snapshot with the SEC's current file |

Ask a question from Python:

```python
from datetime import date
from us_rag.db import connect_ro
from us_rag.query.generate import answer, gemini_generate

with connect_ro() as conn:
    a = answer(conn, "What was Apple's total net sales for fiscal year 2025?", as_of=date(2026, 3, 1))
    print(a.status, a.text, a.citations)
    b = answer(conn, "What risks did Apple disclose about its supply chain?",
               as_of=date(2026, 3, 1), generate_fn=gemini_generate)   # prose via Gemini
```

## 4b. Working on a change

Every change reaches `main` through a pull request (ADR-0021):

```bash
git switch main && git pull
git switch -c l1/tracing            # <step>/<short-name>
# … edit, then locally:
make check                          # lint + unit tests (no Docker needed)
make test-integration               # needs `make up`
git push -u origin l1/tracing       # then open the pull request on GitHub
# after the 4 checks are green: "Squash and merge" on GitHub, then delete the branch
git switch main && git pull && git branch -D l1/tracing   # -D: a squash merge doesn't look "merged" to git
```

Gates 2–5 don't run in CI yet (E2); run the ones your change touches locally before merging.

## 5. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://usrag:usrag@localhost:5433/usrag` | owner connection |
| `DATABASE_URL_RO` | `postgresql://usrag_ro:usrag_ro@localhost:5433/usrag` | read-only connection |
| `SEC_EDGAR_USER_AGENT` | — (required, must contain `@`) | EDGAR fair access |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | model default `gemini-2.5-flash-lite` (answers) | ADR-0008 |
| `TIINGO_API_KEY` | — | prices |
| `US_RAG_EMBED_DEVICE` / `_BATCH` / `_MAXLEN` | `cpu` / `8` / `2048` | ADR-0011 |

## 6. Known problems and fixes

| Symptom | Cause | Fix |
|---|---|---|
| Connected, but tables are missing or wrong | Another Postgres owns port 5432 on this Mac | The project uses **5433**; check `DATABASE_URL` |
| `Cannot connect to the Docker daemon` | Docker Desktop not running | Start Docker Desktop, then `make up` |
| Embedding crashes partway (out of memory) | GPU (MPS) shares 8 GB with the display | Keep `US_RAG_EMBED_DEVICE=cpu` (default); rerun — it resumes |
| Gemini `429 RESOURCE_EXHAUSTED` | Free-tier daily quota | Use `gemini-2.5-flash-lite`; rerun tomorrow — extraction resumes |
| `make gates` stops at phase_02 | Human/key items open (expected) | Run later gates directly: `make gate PHASE=5` |
| `ModuleNotFoundError: yaml` | pyyaml only arrives with the `embed` group | `uv sync --group embed` |
| Phase 1 fails on a fiscal date mismatch | Seed row and XBRL-derived row disagree | Never "fix" by formula (U8): check the filing, correct the seed, record an ADR |

## 7. Rebuilding from scratch

`make down`, remove the Docker volume `db_data`, `make up`, then sections 2–3. `blobs/` is
reused (nothing is re-downloaded that is already on disk).
