# Phase 0 in plain words — the rails

*(Terms in this doc: gate, fixture, CI, container, seed → all in `glossary.md`.)*

## The problem this phase solves

Before building anything real, we needed a way to **know, mechanically, whether
each step is actually done and still working**. Solo projects (and AI-built
projects especially) rot in a specific way: something built in week 1 quietly
breaks in week 4 and nobody notices until it poisons everything downstream.

## The idea

Every phase gets a **gate**: a script that checks, with zero human judgment,
whether that phase's promises hold. `make gate PHASE=0` runs one; `make gates`
runs *all of them, every time* — so if Phase 5 work breaks Phase 1, we know the
same day. A robot checklist that never gets tired or generous.

## What was actually built

1. **A database in a box.** Postgres runs in a Docker container — a sealed,
   versioned box that starts identically on any machine (`make up`). We hit one
   real-world snag: your Mac already runs another postgres on the same "port"
   (think: apartment number), and connections went to the wrong database while
   everything *looked* healthy. Our box now uses port 5433. Lesson: when a
   healthy system gives weird answers, check *which* system you're talking to.
2. **The ten companies, resolved and frozen.** We picked 10 US companies (chosen
   so their quirks stress-test us: weird fiscal years, a bank, a stock split).
   Their SEC ID numbers (CIKs) were resolved from an official SEC file that we
   downloaded once and **committed to the repo** (a *fixture*) — so tests never
   depend on the SEC website being up, and the result is reproducible forever.
3. **`universe.json` is generated, never hand-edited.** The gate re-derives it
   from the frozen SEC file and compares byte-for-byte. If anyone hand-edits it,
   the build fails. Rule of thumb worth keeping: *derived files should carry
   their derivation, and the derivation is the test.*
4. **Identification for the SEC.** The SEC requires programs to identify
   themselves with a contact email. That lives in `.env`, and the gate refuses
   to pass without it — a legal requirement turned into a build requirement.

## The surprise: XOM

The official SEC file said ticker XOM belongs to a company that had existed for
*nine days* — ExxonMobil had just restructured into a new holding company
(2026-07-01), and the new entity has never filed an annual report. All the
reports we need live under the *old* company ID. We pinned an explicit,
documented override.

Why this matters beyond Exxon: **even "what company does this ticker mean" is a
time-dependent question.** That's the project's whole thesis showing up
uninvited: facts drift over time, and systems that store only "the current view"
silently corrupt history.

## Exercise 0 — break it on purpose (~15 min, no code)

The goal is to *feel* what the gates protect.

1. Run `make gates` — everything green.
2. Open `universe.json`, change one digit of any CIK, save.
3. Run `make gate PHASE=0` — read which check fails and what its message says.
4. Restore with `git checkout universe.json`, re-run, green again.
5. Now delete one line from `.env` (`SEC_EDGAR_USER_AGENT=...`), run the gate,
   read the failure, put it back.
6. Bonus: `make down`, run the gate (database check fails), `make up`, green.

**You've consolidated this phase when you can answer:** why is hand-editing
`universe.json` impossible to get away with, even though it's a plain text file
sitting right there?
