# ADR-0021: Engineering track (E1–E3) and a CI that means something

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-27 |
| **Type** | Process |

## Context

Until now every change went straight onto `main`, and the GitHub Actions workflow ran
`run_all.py` against an empty database: it could never pass gate 2, `pyyaml` was not a
declared dependency, and the search model was not installed. A check that is always red
teaches everyone to ignore it. The user wants CI/CD in the project, while keeping RAG
evaluation, ingestion, chunking and search as the main focus.

## Decision

Add a thin engineering track alongside the L-steps:

- **E1 — branches and CI (now).** Trunk-based: `main` is always working; work happens on
  short-lived branches named `<step>/<topic>` and is squash-merged by pull request. One
  workflow runs four independent jobs: `lint` (ruff), `unit` (tests needing no services),
  `integration` (a Postgres + pgvector service; database tests; gates 0 and 1), and
  `secrets` (gitleaks over each pull request's or push's new commits, and over the full
  history weekly and on manual runs). Tests are split automatically: a test that
  uses the `db_url` fixture (directly or via `conn` / `company_id`) is marked
  `integration`. `pyyaml` is declared; CI installs with `uv sync --locked`. A GitHub
  ruleset on `main` requires a pull request and the four checks.
- **E2 — evaluation gates in CI (after M0 sign-off).** A frozen database snapshot
  (versioned with DVC) plus pre-computed embeddings for the golden questions, so gates 3–5
  — recall ratchet, zero look-ahead, exact numbers — run on every pull request.
- **E3 — delivery (with the demo step).** A Docker image built and published on each
  tagged release (`v0.1.0`, …).

The E1 "gate" is the CI workflow itself (a pull request with all four checks green),
not a `backend/gates/e1_*.py` script — a deviation from "each step adds a gate script",
because a script re-checking the workflow file would be ceremony.

Out of scope: staging/production environments, Kubernetes, infrastructure-as-code,
monitoring stacks, and hosting — weeks of work with little signal for RAG roles.

## Consequences

- Gates 2–5 stay local-only until E2; the PR template reminds the author to run them.
- The ruleset is enforced only on a public repository (GitHub Free) or with GitHub Pro;
  if the repo stays private, "red can't merge" is a habit, not a rule.
- Two gitleaks false positives (prose matched by the generic-api-key rule in historical
  docs) are ignored by exact fingerprint in `.gitleaksignore`.
- Order after E1: a small answer-path bug-fix step (the margin rendered as "$0 million",
  "growth" answered as revenue, and the defects listed in `docs/production/lld/answering.md`
  §6), then L1.
