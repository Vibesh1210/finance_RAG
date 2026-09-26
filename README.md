# US Equity Financial RAG

Decision-support RAG over SEC filings, 8-K earnings releases, and market data for a
pinned 10-company US universe. Bitemporal facts store, deterministic SQL for every
number, point-in-time-safe retrieval, gate-driven build.

- **Start here:** `START_HERE.md` (doc map + the plan) · **Current state:** `STATUS.md`
- **Design:** `docs/design_us.md` · **Build detail:** `docs/execution_plan_us.md` · **What's next:** `docs/roadmap_learning.md`
- **Learning track:** `learn/README.md` · **Decisions log:** `DECISIONS.md` · **Working agreement:** `CLAUDE.md`

*(This page is rewritten as the project's front page after M0 sign-off — roadmap step "Showcase 1".)*

## Quick start

```bash
cp .env.example .env       # fill in SEC_EDGAR_USER_AGENT (email required) + keys
make up                    # postgres:16 + pgvector via docker compose
make sync                  # uv sync
make gate PHASE=5          # one step's pass/fail check (5 = the M0 gate)
make gates                 # every check built so far (all must stay green)
```
