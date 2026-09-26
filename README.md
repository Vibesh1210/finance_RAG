# US Equity Financial RAG

Decision-support RAG over SEC filings, 8-K earnings releases, and market data for a
pinned 10-company US universe. Bitemporal facts store, deterministic SQL for every
number, point-in-time-safe retrieval, gate-driven build.

- **Start here:** `START_HERE.md` · **Current state:** `docs/implementation/status.md`
- **How it's built:** `docs/production/` (HLD, LLDs, ADRs, runbook) · **What's next:** `docs/implementation/roadmap.md`
- **Learning track:** `docs/learning_docs/` · **Working agreement:** `CLAUDE.md`

*(This page is rewritten as the project's front page after M0 sign-off — roadmap step "Showcase 1".)*

## Repository layout

- [backend/](backend/README.md): Python source, database migrations, tests, gates, and scripts.
- [frontend/](frontend/README.md): interview UI design and future frontend code.
- `docs/`: shared architecture, learning material, roadmap, and project status.
- Root configuration and datasets support both areas; run `make` and `uv` from this root.

## Quick start

```bash
cp .env.example .env       # fill in SEC_EDGAR_USER_AGENT (email required) + keys
make up                    # postgres:16 + pgvector via docker compose
make sync                  # uv sync
make gate PHASE=5          # one step's pass/fail check (5 = the M0 gate)
make gates                 # every check built so far (all must stay green)
```
