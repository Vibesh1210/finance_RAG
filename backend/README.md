# Backend

Python application code, database definitions, and backend checks live here.

```text
backend/
├── src/us_rag/   ingestion, storage, retrieval, calculations, answering, evaluation
│   └── serve/   reserved for the proposed local HTTP adapter
├── db/          PostgreSQL initialization and migrations
├── tests/       unit and database integration tests
├── gates/       phase verification scripts
└── scripts/     maintenance and data preparation commands
```

Run commands from the **repository root** (`US_rag/`):

```bash
uv sync --group embed       # refresh the editable install after the directory move
make test
make gate PHASE=5
```

The root owns `pyproject.toml`, `uv.lock`, `.env`, Docker Compose, and the Makefile.
Shared data remains in root `fixtures/`, `golden/`, `universe.json`, and ignored `blobs/`.
This preserves stored blob paths and existing local configuration. Python imports remain
`us_rag.*`; the package now installs from `backend/src/us_rag`.

The backend owns exact financial calculations, source selection, historical cutoffs,
database access, model calls, and verification. The frontend consumes structured results;
it does not connect to Postgres or calculate financial answers.

See the [runbook](../docs/production/04_runbook.md),
[architecture](../docs/production/02_hld.md), and
[frontend design](../frontend/docs/interview_ui_design.md).

Historical ADRs, completed plans, and archived walkthroughs retain their original path
spellings. Their former `src/`, `db/`, `tests/`, `gates/`, and `scripts/` directories now
live under `backend/`.
