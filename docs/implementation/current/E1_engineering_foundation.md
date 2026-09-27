# E1 — Engineering foundation: branches, pull requests, working CI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every change reaches `main` through a pull request whose automatic checks (lint, unit tests, integration tests with a real database, gates 0–1, secret scan) must be green — and `main` is protected so a red change cannot merge.

**Architecture:** Trunk-based: `main` is always working; work happens on short-lived branches merged by pull request. One GitHub Actions workflow runs four independent jobs. Tests are split automatically into *unit* (no services) and *integration* (needs Postgres) by which fixtures they use. Gates 2–5 stay out of CI until E2 adds a frozen data snapshot.

**Tech Stack:** GitHub Actions, `astral-sh/setup-uv`, pytest markers, ruff, Postgres 16 + pgvector service container, gitleaks.

**Spec:** the "Design" section below (agreed in conversation on 2026-09-26) + `docs/implementation/roadmap.md` (E-track, added by this plan).

---

## E1 in plain words (read this first)

Today everything is committed straight onto `main`, and the automatic checks on GitHub
("CI") go red for reasons that have nothing to do with the code: the CI database is empty,
one library isn't declared, and the search model isn't installed. A red light that is
always red teaches you to ignore it.

After E1, every change travels like this:

```
new branch ──► commits ──► push ──► pull request ──► 4 automatic checks ──► all green? ──► merge into main
                                                     lint · unit · integration · secrets     │
                                                                                             no ──► blocked
```

- **Lint** — a tool (ruff) reads the code for mistakes like unused imports. Seconds.
- **Unit tests** — the 99 tests that need nothing but Python. About a minute.
- **Integration** — starts a real Postgres, builds the database from scratch, runs the 37
  tests that need it plus gates 0 and 1. A few minutes.
- **Secrets** — scans every commit ever made for leaked passwords or API keys.

**What E1 deliberately does NOT do:** run gates 2–5 in CI (they need the real 41,175 facts
and 7,033 embedded chunks — that's E2's frozen snapshot), build a Docker image or releases
(E3), or put anything online.

---

## Design

| Decision | Choice | Why |
|---|---|---|
| Branching | Trunk-based: `main` + short-lived branches `e1/…`, `l1/…`, `fix/…`; squash-merge | Simplest modern practice; one commit per change on `main`; no long-lived "deployment branch" (releases will be tags, E3) |
| Protection | GitHub **ruleset** on `main`: PR required, the 4 checks required, no force-push, no deletion | Makes "red can't merge" real. Enforced on public repos (free) or with GitHub Pro |
| Test split | Auto-mark tests that use the `db_url` fixture (directly or via `conn` / `company_id`) as `integration` | No per-test markers to forget; a new DB test is classified correctly by construction |
| CI jobs | `lint`, `unit`, `integration`, `secrets` — parallel, independent | A failure names exactly what broke; unit results arrive without waiting for Postgres |
| Dependencies | `pyyaml` declared directly; CI installs with `uv sync --locked` | Today `yaml` only arrives via the optional `embed` group; `--locked` fails CI if `uv.lock` is stale |
| Gates in CI | Gates 0 and 1 only (gate 1 runs the whole test suite against the service DB) | Gates 2–5 need the loaded corpus → E2 |
| The E1 "gate" | The CI workflow itself (a PR with all 4 checks green) — no `backend/gates/e1_*.py` | A script that re-checks the workflow file would be ceremony; recorded in ADR-0021 |

**Measured starting point (2026-09-26, Docker off):** `pytest` → 99 passed, 37 errors, and
every error is `psycopg.OperationalError` (no database). `ruff check` → 2 pre-existing
unused imports (`query/generate.py:29`, `store/migrate.py:9`). Git history scan for API-key
patterns → 0 hits; `.env` never committed.

## Global Constraints

- Python `3.12` (`.python-version`); dependency manager `uv`; lockfile `uv.lock` must stay in sync (`uv sync --locked` in CI).
- Database in CI: `pgvector/pgvector:pg16`, user/password/db `usrag`, `DATABASE_URL=postgresql://usrag:usrag@localhost:5432/usrag`.
- CI is fixtures-only: no call to SEC, Tiingo, Gemini or Hugging Face in any CI job (existing hard rule).
- `SEC_EDGAR_USER_AGENT` in CI is the placeholder `US-rag-CI (ci@users.noreply.github.com)` — never a real address.
- Required check names (used by the ruleset) are exactly: `lint`, `unit`, `integration`, `secrets`.
- No behaviour change to application code in E1; only the two unused imports are removed.
- Every push to GitHub and every GitHub setting change happens only with the user's go-ahead (outward-facing actions).

## Review Focus

- **CI green but checking nothing** — if the marker logic ever deselected everything, pytest exits 5 ("no tests collected") and the job fails; Task 2 verifies the exact split 99 / 37 so a silent drop is visible.
- **A developer without Docker runs `make test`** — expects a clear path: `make test-unit` must pass with Docker stopped (Task 2 checks exactly that).
- **Secret scanner false positives** on public data in `fixtures/` (SEC ticker file, accession numbers) — Task 3 runs gitleaks locally first and adds a narrow allowlist only if it actually fires.
- **Going public exposes commit metadata** — past commits carry the author email; Task 5 tells the user before they flip visibility.
- **Stale lockfile** — adding `pyyaml` without re-locking would make `uv sync --locked` fail; Task 1 re-locks and verifies in a clean environment that mimics CI.

---

## File map

| File | Change | Responsibility |
|---|---|---|
| `pyproject.toml` | modify | declare `pyyaml`; register the `integration` marker |
| `uv.lock` | regenerate | lock `pyyaml` as a direct dependency |
| `backend/src/us_rag/query/generate.py`, `backend/src/us_rag/store/migrate.py` | modify | remove the 2 unused imports |
| `backend/tests/conftest.py` | modify | auto-mark DB tests as `integration` |
| `Makefile` | modify | `lint`, `test-unit`, `test-integration`, `check` targets |
| `.gitignore` | modify | ignore `.serena/` (editor tool config) |
| `.github/workflows/ci.yml` | rewrite | the 4-job workflow |
| `.github/pull_request_template.md` | create | definition-of-done checklist on every PR |
| `docs/production/adr/ADR-0021-engineering-track-and-ci.md` (+ index row) | create | the decisions above |
| `docs/production/03_evaluation_and_testing.md` §1, §6 | modify | describe the real CI |
| `docs/production/04_runbook.md` | modify | "Working on a change" section |
| `docs/implementation/roadmap.md`, `status.md` | modify | add the E-track; mark E1 |
| `CLAUDE.md` | modify | "work on a branch, merge by PR" |
| `docs/learning_docs/08_how_changes_get_checked.md` | create | plain-words learning doc |
| `docs/learning_docs/glossary.md` | modify | CI terms |

---

### Task 0: Pre-flight (baseline + clean starting point)

**Files:** none changed (commits the already-staged doc restructure).

- [ ] **Step 1: [HUMAN] Start Docker Desktop**, then:

Run: `cd US_rag && make up`
Expected: `Container us_rag_db  Healthy`

- [ ] **Step 2: Record the baseline**

Run: `make test`
Expected: `136 passed` (all tests, database available)

Run: `make gate PHASE=0 && make gate PHASE=1 && make gate PHASE=4 && make gate PHASE=5`
Expected: each ends `all N checks passed`. (Gate 2 = 5/9 and gate 3 = 4/5 are known human items — don't run `make gates`, it stops at 2.)
If anything else fails, stop: the doc restructure broke something — fix before E1.

- [ ] **Step 3: [HUMAN approves] Commit the staged doc restructure on `main`**

```bash
git status --short | head        # review: only docs/ + comment-only code changes
git commit -m "docs: restructure into production / learning / implementation (ADR-0019, ADR-0020)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Create the E1 branch**

```bash
git switch -c e1/engineering-foundation
```

---

### Task 1: Declare dependencies and clean the lint baseline

**Files:**
- Modify: `pyproject.toml` (`[project].dependencies`)
- Regenerate: `uv.lock`
- Modify: `backend/src/us_rag/query/generate.py:29`, `backend/src/us_rag/store/migrate.py:9`
- Modify: `.gitignore`, `Makefile`

- [ ] **Step 1: Prove the CI-environment failure first**

```bash
UV_PROJECT_ENVIRONMENT="$TMPDIR/e1-ci-venv" uv sync
"$TMPDIR/e1-ci-venv/bin/python" -c "import us_rag.eval.golden"
```
Expected: `ModuleNotFoundError: No module named 'yaml'` (the default install lacks it — this is what CI sees).

- [ ] **Step 2: Declare `pyyaml` and re-lock**

In `pyproject.toml`, `[project].dependencies` becomes:

```toml
dependencies = [
    "psycopg[binary]>=3.2",
    "httpx>=0.27",
    "lxml>=6.1.1",
    "google-genai>=1.0",
    "pyyaml>=6.0",
]
```

```bash
uv lock
UV_PROJECT_ENVIRONMENT="$TMPDIR/e1-ci-venv" uv sync --locked
"$TMPDIR/e1-ci-venv/bin/python" -c "import us_rag.eval.golden; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Remove the two unused imports**

```bash
uv run ruff check backend/src backend/gates backend/scripts backend/tests
```
Expected: `Found 2 errors.` (F401 `MetricResult` in `query/generate.py`, F401 `Path` in `store/migrate.py`)

```bash
uv run ruff check --fix backend/src/us_rag/query/generate.py backend/src/us_rag/store/migrate.py
uv run ruff check backend/src backend/gates backend/scripts backend/tests
```
Expected: `All checks passed!`

- [ ] **Step 4: Ignore the editor config and add make targets**

Append to `.gitignore`:

```
# editor/assistant tool config (Serena)
.serena/
```

```bash
git rm -r --cached -q .serena
```

In `Makefile`, replace the first line and add targets after `test:`:

```make
.PHONY: up down sync migrate seed test test-unit test-integration lint check gate gates verify-live
```

```make
test-unit:
	uv run pytest -q -m "not integration"

test-integration:
	uv run pytest -q -m integration

lint:
	uv run ruff check backend/src backend/gates backend/scripts backend/tests

check: lint test-unit
```

(`test-unit` / `test-integration` work after Task 2 registers the marker.)

- [ ] **Step 5: Verify nothing regressed**

Run: `make test`
Expected: `136 passed`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock backend/src/us_rag/query/generate.py backend/src/us_rag/store/migrate.py .gitignore Makefile
git commit -m "e1: declare pyyaml, clean lint baseline, untrack .serena, make targets

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Split tests into unit and integration automatically

**Files:**
- Modify: `pyproject.toml` (existing `[tool.pytest.ini_options]`)
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Produces: pytest marker `integration`; commands `pytest -m "not integration"` (unit) and `pytest -m integration` used by Task 3's CI jobs.

- [ ] **Step 1: See the current behaviour**

Run: `uv run pytest -q -m integration`
Expected: `136 deselected` and "no tests ran" (exit code 5) — no test carries the marker yet.

- [ ] **Step 2: Register the marker**

Extend the existing `[tool.pytest.ini_options]` in `pyproject.toml`, retaining test discovery:

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
markers = [
    "integration: needs the Postgres test database (auto-applied in backend/tests/conftest.py)",
]
```

- [ ] **Step 3: Auto-mark database tests**

Append to `backend/tests/conftest.py`:

```python
def pytest_collection_modifyitems(config, items):
    """A test that touches the database — directly via `db_url`, or through `conn` /
    `company_id`, which depend on it — is an *integration* test; everything else is a
    *unit* test that runs with no services. Marking by fixture keeps the split automatic:
    a new DB test is classified correctly without anyone remembering a marker."""
    for item in items:
        if "db_url" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.integration)
```

- [ ] **Step 4: Verify the split is exact — with Docker stopped**

```bash
make down
uv run pytest -q -m "not integration"
```
Expected: `99 passed, 37 deselected` — no errors (unit tests need no database).

```bash
uv run pytest -q -m integration
```
Expected: `37 errors` — all `psycopg.OperationalError` (proves exactly the DB tests were selected).

- [ ] **Step 5: Verify with the database**

```bash
make up
make test-integration
make test
```
Expected: `37 passed, 99 deselected`, then `136 passed`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml backend/tests/conftest.py
git commit -m "e1: auto-split tests into unit and integration by fixture

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The four-job CI workflow + secret scan

**Files:**
- Rewrite: `.github/workflows/ci.yml`
- Create (only if Step 1 finds false positives): `.gitleaks.toml`

**Interfaces:**
- Consumes: `make`-equivalent commands from Tasks 1–2 (`ruff check …`, `pytest -m …`).
- Produces: GitHub check names `lint`, `unit`, `integration`, `secrets` — required by Task 5's ruleset.

- [ ] **Step 1: Run the secret scanner locally over the full history**

```bash
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest git /repo --no-banner
```
Expected: `no leaks found`.
If it reports findings: open each one. A real secret → **stop and tell the user** (it must be rotated, not hidden). A false positive in public data (e.g. under `fixtures/`) → create `.gitleaks.toml`:

```toml
[extend]
useDefault = true

[allowlist]
description = "Public SEC reference data, not secrets"
paths = ['''^fixtures/company_tickers\.json$''']
```
and re-run until clean.

- [ ] **Step 2: Replace `.github/workflows/ci.yml`**

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

# a newer push to the same branch cancels the older, now-pointless run
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run ruff check backend/src backend/gates backend/scripts backend/tests

  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run pytest -q -m "not integration"

  integration:
    runs-on: ubuntu-latest
    services:
      db:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: usrag
          POSTGRES_PASSWORD: usrag
          POSTGRES_DB: usrag
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U usrag -d usrag"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 12
    env:
      DATABASE_URL: postgresql://usrag:usrag@localhost:5432/usrag
      # placeholder proves the config plumbing; the real User-Agent lives in local .env only
      SEC_EDGAR_USER_AGENT: US-rag-CI (ci@users.noreply.github.com)
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked
      # service containers can't mount backend/db/init/, so the extension is enabled explicitly (ADR-0002)
      - run: psql "$DATABASE_URL" -c 'CREATE EXTENSION IF NOT EXISTS vector;'
      - run: uv run pytest -q -m integration
      # Gates 2-5 need the loaded corpus (facts, embedded chunks); they join CI in E2 via a
      # frozen data snapshot (ADR-0021). Gate 1 re-runs the whole test suite as one of its checks.
      - run: uv run python backend/gates/phase_00.py
      - run: uv run python backend/gates/phase_01.py

  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # scan every commit, not just the latest
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 3: Check the file parses**

Run: `uv run python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); print(sorted(d['jobs']))"`
Expected: `['integration', 'lint', 'secrets', 'unit']`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml   # plus .gitleaks.toml only if Step 1 created it
git commit -m "e1: CI as four jobs — lint, unit, integration (gates 0-1), secret scan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: PR template + docs + ADR-0021 + learning doc

**Files:**
- Create: `.github/pull_request_template.md`
- Create: `docs/production/adr/ADR-0021-engineering-track-and-ci.md`; add its row to `docs/production/adr/README.md`
- Modify: `docs/production/03_evaluation_and_testing.md` (§1 and §6), `docs/production/04_runbook.md`
- Modify: `docs/implementation/roadmap.md`, `docs/implementation/status.md`, `CLAUDE.md`
- Create: `docs/learning_docs/08_how_changes_get_checked.md`; modify `glossary.md`, and `00_how_to_understand_this_project.md` §8 map row

- [ ] **Step 1: PR template** — `.github/pull_request_template.md`:

```markdown
## What and why

<!-- one or two sentences; link the plan in docs/implementation/current/ -->

## Definition of done (docs/implementation/roadmap.md)

- [ ] CI green: lint · unit · integration · secrets
- [ ] Gates still green locally that CI can't run yet: `make gate PHASE=2..5` (known human items excepted)
- [ ] LLD updated for every component touched (`docs/production/lld/`)
- [ ] New decision or deviation → new ADR
- [ ] Learning doc written/updated (`docs/learning_docs/`)
- [ ] `docs/implementation/status.md` updated
```

- [ ] **Step 2: ADR-0021** — `docs/production/adr/ADR-0021-engineering-track-and-ci.md` in the standard format (Status Accepted, Date 2026-09-26, Type Process). Context: CI red for environment reasons; user wants CI/CD but RAG evals remain the focus. Decision: add an E-track (E1 branches + PR + four-job CI with gates 0–1; E2 frozen DB snapshot via DVC + precomputed question embeddings so gates 3–5 run in CI; E3 Docker image + tagged releases); trunk-based with squash merges; ruleset on `main`; tests auto-split by the `db_url` fixture; the E1 "gate" is the CI workflow itself (deviation from "each step adds `backend/gates/<step>.py`"); heavy DevOps (staging environments, Kubernetes, infrastructure-as-code, hosting) explicitly out of scope. Consequences: gates 2–5 remain local-only until E2; private repo on the Free plan cannot enforce the ruleset. Add the index row after ADR-0020.

- [ ] **Step 3: Production docs**
  - `03_evaluation_and_testing.md` §1: add "Tests are auto-split: `make test-unit` (99, no services) and `make test-integration` (37, needs Postgres); `make test` runs both." §6: replace "Known risks" with the four jobs, what each runs, and "gates 2–5 join CI in E2".
  - `04_runbook.md`: new section **"Working on a change"**:

```bash
git switch main && git pull
git switch -c l1/tracing            # <step>/<short-name>
# … edit, then locally:
make check                          # lint + unit tests (no Docker needed)
make test-integration               # needs `make up`
git push -u origin l1/tracing       # then open the pull request on GitHub
# after the 4 checks are green: "Squash and merge" on GitHub, then delete the branch
```

- [ ] **Step 4: Roadmap, status, CLAUDE.md**
  - `roadmap.md`: add rows to "At a glance" — `E1` before L1, `E2` after M0 sign-off, `E3` with Showcase 2 — and a section "### E-track — engineering foundation" with one paragraph per step (content as in ADR-0021) and the note "L2's chunk-size experiments are tracked with DVC (from E2)".
  - `status.md`: add E1/E2/E3 rows to the step table; E1 ▶ in progress; remove the "CI risks" housekeeping bullet once Task 5 is green.
  - `CLAUDE.md`, Protocol paragraph: add "Work on a branch named `<step>/<topic>`; never commit to `main` directly; merge by pull request with all checks green."

- [ ] **Step 5: Learning doc** — `docs/learning_docs/08_how_changes_get_checked.md`, following the standard shape (problem with a real example → one flow → walk through naming files → rules → check-yourself with hidden answers). Required content:
  1. *The problem:* the 2026-09-26 finding — CI red for reasons unrelated to code (empty database, undeclared `pyyaml`), so red meant nothing.
  2. *The flow to remember:* the branch → PR → 4 checks → merge diagram from the top of this plan.
  3. *Walk-through:* `.github/workflows/ci.yml` job by job; `backend/tests/conftest.py` auto-marking; `make check` vs CI; what a ruleset is.
  4. *Rules:* never commit to `main`; a red check is never "just CI"; CI never calls external data APIs.
  5. *Check yourself (4 questions):* why unit and integration are separate jobs · why gates 2–5 aren't in CI yet · what `--locked` catches · why a secret found by the scanner must be rotated, not just deleted.
  - `glossary.md`: add CI job/runner, workflow, pull request, squash merge, ruleset, lint, lockfile.
  - `00_how_to_understand_this_project.md` §8: add the row `| 08 | How changes get checked | branches, pull requests, CI, unit vs integration tests | production/03_evaluation_and_testing.md §6 | .github/, backend/tests/conftest.py |`, and renumber the "08+" row to "09+".

- [ ] **Step 6: Commit**

```bash
git add .github/pull_request_template.md docs CLAUDE.md
git commit -m "e1: PR template, ADR-0021, CI docs, runbook workflow, learning doc 08

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Go live on GitHub — first PR, proof that red blocks, protect `main`

**Files:** none (GitHub actions and settings).

- [ ] **Step 1: [HUMAN approves] Push the branch and open the PR**

```bash
git push -u origin e1/engineering-foundation
```
Then on GitHub: *Compare & pull request* → base `main` → the template fills the description → *Create pull request*.
Expected: 4 checks start: `lint`, `unit`, `integration`, `secrets`; all green within ~5 minutes.
If one fails: read its log on the PR's *Checks* tab, fix on the branch, push again.

- [ ] **Step 2: Prove red is red** — on the same branch:

```bash
printf '\nimport json\n' >> backend/src/us_rag/env.py   # an unused, misplaced import: lint must fail
git commit -am "tmp: prove lint blocks" && git push
```
Expected: `lint` ❌ on the PR. Then undo:

```bash
git revert --no-edit HEAD && git push
```
Expected: `lint` ✅ again.

- [ ] **Step 3: [HUMAN] Decide repository visibility**

Rulesets are only enforced on **public** repos with GitHub Free (or any repo with GitHub Pro — free for students via GitHub Education).
Before going public, know: (a) the secret scan over the full history is green; (b) commit author metadata becomes visible: all existing commits carry the real email address, and that is permanent once public (hiding it would need a history rewrite + force-push, before the ruleset exists). To stop exposing it from now on, do **both**: GitHub → *Settings → Emails → Keep my email addresses private* (this also sets the author of squash-merge commits), and locally `git config user.email <id>+Vibesh1210@users.noreply.github.com` (the exact address is shown on that settings page). Don't enable "Block command line pushes that expose my email" until the local config is changed, or your pushes will be rejected; (c) `.env` and `blobs/` were never committed.
Choose: **public** (recommended — a portfolio repo must be visible anyway), **Pro**, or **stay private** (then protection is a habit, not enforced).

- [ ] **Step 4: [HUMAN] Create the ruleset** (if public or Pro)

GitHub → repo *Settings → Rules → Rulesets → New branch ruleset*:
- Name `protect-main`; Enforcement **Active**; Target branches: *Include default branch*
- ✅ Restrict deletions · ✅ Block force pushes
- ✅ Require a pull request before merging (required approvals: **0** — solo project)
- ✅ Require status checks to pass → add `lint`, `unit`, `integration`, `secrets`
- Save.

Verify: `git push origin HEAD:main` from any branch → rejected by the ruleset.

- [ ] **Step 5: [HUMAN] Merge** — on the PR: *Squash and merge* → *Delete branch*. Then locally:

```bash
git switch main && git pull && git branch -D e1/engineering-foundation   # -D: squash merges don't look "merged" to git
```

- [ ] **Step 6: Close E1** — move this file to `docs/implementation/completed/E1_engineering_foundation.md`, mark E1 ✅ in `status.md`, drop the CI-risk bullet — on a new branch `e1/close`, via PR (the first change to use the new flow end to end).

---

## E1 is done when

1. A PR shows `lint`, `unit`, `integration`, `secrets` all green, and Step 5.2 showed a red check.
2. `make test-unit` passes with Docker stopped (99); `make test-integration` passes with it running (37).
3. `main` is protected by the ruleset — or the user chose "stay private" and that is recorded in `status.md`.
4. ADR-0021, production docs, roadmap, status, `CLAUDE.md` and learning doc 08 are updated.
