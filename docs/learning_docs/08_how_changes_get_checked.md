# 08 · How changes get checked — branches, pull requests, CI

Every other learning doc is about how the system *answers questions*. This one is about
how the system *stays correct while it changes* — the part of software engineering that
makes a project trustworthy to someone who has never met you.

About 15 minutes. Engineering twin: `docs/production/03_evaluation_and_testing.md` §6.

---

## 1. The problem — a red light that is always red

On 2026-09-26 the automatic checks on GitHub had been failing on every push. Not because
the code was broken — because of three things that had nothing to do with the code:

```
  GitHub's check machine had…            so…
  ─────────────────────────────          ────────────────────────────────────────────
  an EMPTY database                  ──► gate 2 (which needs 41,175 loaded facts) always failed
  no `pyyaml` library                ──► any code reading the test-question files crashed on import
  no 2 GB search model               ──► the search checks could never run
```

A warning light that is always on teaches you to ignore it. Then, the day something *does*
break, nobody notices. E1 fixed that: the checks now run only what they can honestly run,
and they are green — so a red one means something.

---

## 2. The flow to remember

```
  1 BRANCH           2 WORK               3 PULL REQUEST          4 CHECKS (automatic)           5 MERGE
  ┌─────────────┐    ┌──────────────┐     ┌────────────────┐     ┌─────────────────────────┐    ┌──────────────┐
  │ a private    │──►│ edit, commit, │──►│ "please merge  │──►│ lint        ~30 s        │──►│ all green?   │
  │ copy of main │   │ `make check`  │   │  my branch      │   │ unit        ~1 min       │   │  yes → merge │
  │ l1/tracing   │   │ locally       │   │  into main"     │   │ integration ~3 min       │   │  no  → fix,  │
  └─────────────┘    └──────────────┘     └────────────────┘   │ secrets     ~30 s        │   │   push again │
                                                                └─────────────────────────┘    └──────────────┘
                                                                                                       │
                                                                          main is always working ◄─────┘
```

**Memory hook: "branch, check, merge — main is never broken."**

---

## 3. Walk through it

### Branch — a safe copy

`git switch -c l1/tracing` makes a copy of `main` called `l1/tracing`. Everything you do
there is invisible to `main` until you ask to merge. Name = `<step>/<topic>`.

### Pull request (PR) — asking to merge

You push the branch to GitHub and open a *pull request*: "please merge `l1/tracing` into
`main`". The PR page shows your changes, a checklist (from `.github/pull_request_template.md`),
and — most importantly — the four checks.

### The four checks — `.github/workflows/ci.yml`

GitHub starts a fresh, empty Linux machine (a *runner*) for each check (a *job*), installs
the project exactly as locked in `uv.lock`, and runs one thing:

| Job | Runs | Catches | Needs |
|---|---|---|---|
| `lint` | `ruff check` — reads the code without running it | unused imports, obvious mistakes | nothing |
| `unit` | the 99 tests that need nothing but Python | logic bugs in pure functions (RRF, the verifier, fiscal parsing …) | nothing |
| `integration` | starts Postgres, runs the 37 database tests, then gates 0 and 1 | broken migrations, the append-only trigger, as-of reads, seeds | a database service |
| `secrets` | gitleaks over **every commit ever made** | an API key accidentally committed | the full git history |

### How a test knows it's "integration" — `backend/tests/conftest.py`

Tests that need the database ask for it through a *fixture* called `db_url` (directly, or
through `conn` / `company_id`, which depend on it). One small function looks at every test
before it runs and labels those as `integration`:

```
  test asks for db_url (or conn, company_id)?   yes ──► label "integration"  (needs Postgres)
                                                no  ──► stays "unit"         (runs anywhere)
```

Nobody has to remember to label a new test — asking for the database *is* the label.
That's why `make test-unit` works with Docker switched off (99 pass) and
`make test-integration` needs it (37 pass).

### Locked installs — `uv sync --locked`

`uv.lock` records the exact version of every library. `--locked` makes CI *refuse* to run
if `pyproject.toml` and `uv.lock` disagree — so "works on my machine, breaks in CI" because
of a forgotten library can't happen silently. That's precisely the `pyyaml` problem from §1.

### Merge — and why `main` is protected

When all four are green you press **Squash and merge**: the branch's commits become one
tidy commit on `main`. A GitHub **ruleset** on `main` makes this the *only* way in: no
direct pushes, no merging while a check is red.

---

## 4. The rules

- **Never commit to `main` directly.** Branch, then pull request.
- **A red check is never "just CI".** Either the code is wrong or the check is wrong — both
  get fixed, neither gets ignored.
- **CI never calls the internet for data.** No SEC, no Tiingo, no Gemini — only frozen
  inputs, so a check result depends on the code alone.
- **A leaked secret is rotated, not just deleted.** Deleting it from the latest version
  leaves it in the history, where anyone can find it.

What CI does **not** run yet: gates 2–5. They need the real loaded data (facts, embedded
chunks). E2 adds a frozen copy of the database so they can join CI.

---

## 5. Check yourself

<details>
<summary><b>1.</b> Why are unit and integration tests separate jobs instead of one?</summary>

Unit tests need nothing, so they give an answer in about a minute without starting a
database; if they fail, the problem is in pure logic. Integration tests need Postgres and
take longer; if only they fail, the problem is in database code. Separate jobs tell you
*where* to look — and a laptop without Docker can still run the unit half.
</details>

<details>
<summary><b>2.</b> Why aren't gates 2–5 in CI yet?</summary>

They check the loaded data and search quality — 41,175 facts and 7,033 embedded chunks.
CI starts with an empty database, and rebuilding the data would mean downloading from the
SEC (breaks the offline rule) and hours of embedding. E2 fixes it with a frozen snapshot.
</details>

<details>
<summary><b>3.</b> What does <code>uv sync --locked</code> catch?</summary>

A mismatch between the libraries the project says it needs (`pyproject.toml`) and the exact
versions recorded (`uv.lock`) — e.g. someone adds a library but forgets to re-lock. CI
fails immediately instead of installing something different from your laptop.
</details>

<details>
<summary><b>4.</b> The secret scanner finds a real API key in a commit from last month. Is deleting the file enough?</summary>

No. Git keeps every old version, so the key is still readable in the history — and bots
scan public repos for exactly this. The key must be **revoked and replaced** at the
provider; cleaning the history is secondary.
</details>

---

## 6. Optional hands-on (10 minutes)

On a throwaway branch, add `import json` as the last line of `backend/src/us_rag/env.py`,
run `make lint`, and read the error. Then `git checkout backend/src/us_rag/env.py` and run
it again. That's exactly what the `lint` job will do to a pull request.
