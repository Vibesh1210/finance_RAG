# US Equity Financial RAG

Decision-support RAG over SEC filings, 8-K earnings releases, and market data for a
pinned 10-company US universe. Bitemporal facts store, deterministic SQL for every
number, point-in-time-safe retrieval, gate-driven build.

- **Design:** `docs/design_us.md` · **Build order:** `docs/execution_plan_us.md` (14 phases, 0–13)
- **Per-phase writeups:** `phases_docs/`
- **Decisions log:** `DECISIONS.md` · **Working agreement:** `CLAUDE.md`

## Quick start

```bash
cp .env.example .env       # fill in SEC_EDGAR_USER_AGENT (email required) + keys
make up                    # postgres:16 + pgvector via docker compose
make sync                  # uv sync
make gate PHASE=0          # current phase's gate
make gates                 # every phase gate so far (regression rule)
```
