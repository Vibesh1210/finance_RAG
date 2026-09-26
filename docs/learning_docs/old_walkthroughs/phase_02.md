> **Old walkthrough — being replaced.** Parts of this no longer match the code; see `README.md` in this folder before relying on it.

# Phase 2 in plain words — filling the pantry (ingestion)

*(Terms: ingestion, accession, iXBRL, companyfacts, chunk, embedding, rate limiter,
idempotent, as-of/knowledge_time → `glossary.md`. Builds on the Phase 1 spine.)*

Phase 1 built the *rules* for storing facts. Phase 2 actually **goes and gets the data** —
from the SEC — and puts it where each kind belongs. Nothing here answers a question yet;
it stocks the shelves the later phases cook from.

## Idea 1: one filing has two completely different kinds of content

A 10-K is both a pile of **numbers in tables** (revenue, EPS, assets) and pages of
**prose** (risk factors, management discussion). These want opposite homes:

- **Numbers → the facts table** (Phase 1's spine), so they can be looked up *exactly*.
- **Prose → text "chunks" + embeddings**, so they can be *searched by meaning*.

So one parse of a filing fans out to *both* stores. Numbers you never want a search
engine to approximate; prose you never want to force into a spreadsheet.

## Idea 2: be a polite citizen of someone else's server

The SEC gives EDGAR away for free but asks callers to identify themselves and not hammer
it. The client hard-codes a contact **User-Agent** and a **rate limiter** that paces
requests *below* the cap — and *counts its own behaviour* so a gate can later prove we
never misbehaved. This isn't optional politeness; abusing EDGAR gets you blocked.

## Idea 3: re-running must not duplicate (idempotent)

Backfills get interrupted and restarted. Every document is keyed by its **accession**
(the SEC's unique filing id), so re-fetching a filing already on disk is a no-op, not a
second copy. Same idea for facts: a re-run doesn't double them.

## Idea 4: chop prose along its seams, never across them

Search works on bite-sized "chunks." But if a chunk mixes *Risk Factors* with *Management
Discussion*, a search for risks pulls back half an answer about something else. So
chunking is **heading-aware**: it packs paragraphs up to a size budget (~800 tokens) with
a little overlap, and **never crosses a section boundary**. Each chunk also inherits the
filing's **knowledge_time** — so the "no looking into the future" rule from Phase 1 covers
prose too, not just numbers.

## Idea 5: the numbers came from a machine-readable feed, the prose from the HTML

The exact figures come from the SEC's structured `companyfacts` feed (already tagged, e.g.
`Revenues`). The prose comes from parsing the filing's HTML into sections. Two pipelines,
one unified schema, everything keyed to the same company id (Phase 1's security master).

## A real bug worth remembering — the embedding memory spike

Turning 7,000 chunks into "meaning fingerprints" (embeddings) kept crashing this 8 GB
laptop. The cause wasn't the amount of data — it was that the embedding library defaulted
to the Mac's **GPU**, which shares the same 8 GB as the screen, and a big batch of long
passages overflowed it. Fix: run on the ordinary CPU, cap how long any one passage can be
(measured from the real data so *nothing* gets cut), and shrink the batch. Lesson: the
number in a status file (`128 embedded` = exactly two batches) often *is* the diagnosis.

## What "verified" means here

The Phase 2 gate has nine checks. Five are mechanical and green (corpus counts, fiscal
calendars, section boundaries, the fair-access proof, the "dates beat fiscal labels"
rule). Four need a **human** to read the actual filings and confirm the numbers — because
the whole system's trust rests on the loaded data being right, and a machine shouldn't
bless its own input. That's the `verification_guide.md` checklist.

## Exercise — the heading-aware packer (~30 min)

The core of chunking in ~12 lines of pure Python, no database:

```
uv run python learn/exercises/phase02_chunk_exercise.py
```

Implement `pack()` (greedy packing to a token budget) until every check prints PASS.
When stuck, read `chunk_paragraphs` in `src/us_rag/ingest/narrative.py`.

**You've consolidated this phase when you can answer, in your own words:**
1. Why do the numbers and the prose from one filing go to two different stores?
2. What breaks if a chunk spans two sections of a filing?
3. Why must a re-run of the backfill be idempotent — what would go wrong otherwise?
