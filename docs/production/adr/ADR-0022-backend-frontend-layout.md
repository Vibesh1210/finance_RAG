# ADR-0022: Separate backend and frontend directories

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-26 |
| **Type** | Architecture |

## Context

The user requested a dedicated frontend folder for the interview UI documentation and
a clear separation of backend and frontend code. The existing Python project occupied
root `src/`, `db/`, `tests/`, `gates/`, and `scripts/`.

ADR-0021 is reserved by the existing E1 engineering plan; this change does not implement
or accept that plan's proposed CI changes.

## Decision

Move Python source, database definitions, tests, gates, and scripts under `backend/`.
Place the interview UI design in `frontend/docs/interview_ui_design.md`; future browser
code and its package configuration live in `frontend/`.

Keep Python project configuration, lockfile, `.env`, Makefile, Docker Compose, shared
fixtures/golden banks, universe configuration, and raw blobs at the repository root.
The package remains `us_rag`, installed from `backend/src/us_rag`. Root discovery,
migration lookup, gate/script entry points, packaging, CI paths, and the Compose init
mount are updated for the new layout. Migration SQL and data remain unchanged.

Shared architecture, learning, roadmap, and status docs stay in `docs/`. Frontend-specific
plans and design docs are the explicit exception to the earlier three-section layout.
Historical ADRs and archived/completed plans retain their original paths; current docs
use the new paths.

## Consequences

Root `make` commands remain the entry points. Existing editable Python installations
must be refreshed after this move. Data paths and the database volume are preserved.
The frontend has documentation only; this directory split does not choose its framework,
implement the proposed HTTP adapter, or change the roadmap order.
