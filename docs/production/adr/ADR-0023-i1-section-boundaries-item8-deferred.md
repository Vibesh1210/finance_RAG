# ADR-0023: I1 inserted before sign-off; its guard lives in gate 2; Item 8 notes not extracted

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-10-23 |
| **Type** | Scope |

## Context

On 2026-09-27, about 420 chunks (6% of the index) were found carrying the wrong section
label: JPM's and DE's caption-located sections ran to the end of the document, and
XOM's MD&A opened with a contents list. The M0 sign-off freezes the score baselines, so
fixing chunks after it would have meant re-baselining. The roadmap had no step for it.

The original design (§3, "Section extraction targets Item 1, 1A, 7, 7A, and Item 8
notes") also asked for the financial-statement notes. M0 never extracted them, and the
omission was never recorded. Measured on 2026-10-23 over the cached 10-Ks: the 14 whose
Item 8 the heading pass finds would add 665 chunks (34% on top of the 1,942 kept from
10-Ks today). DE, JPM and NVDA would need new caption-located extraction, the kind I1
just fixed, and XOM's Item 8 is a one-chunk cross-reference. With the 10-Q statements
(Part I Item 1), the estimate is about 2,500 chunks, +35% of the index. No golden
question points to Item 8.

## Decision

1. **I1 (ingestion quality) is a step before sign-off**, in the same track as E1/B1:
   fix the caption-fallback section boundaries, guard them, rebuild only the affected
   filings. Plan: `docs/implementation/completed/I1_ingestion_quality.md`.
2. **I1's gate is gate 2 check 4b** (`check_section_audit`), not a separate
   `backend/gates/I1.py`. Section boundaries are an ingestion property, gate 2 already
   owns them (check 4), and the audit runs over the same database state.
3. **Item 8 notes (and 10-Q Part I Item 1) are not extracted for now.** The statement
   tables are numbers the numbers lane already owns through XBRL facts; extraction for
   four of ten companies would add fragile caption logic; and a +35% index right before
   the baseline freeze would move every retrieval score with no golden question to
   justify it.

## Consequences

- Questions about accounting policies, litigation, debt terms or segment notes find only
  what MD&A says about them. Segment questions keep using MD&A text (ADR-0013).
- Revisit in L2: chunking variants are re-embedded anyway, and the quote-level answer
  key can measure whether notes help or crowd out. Tracked in
  `docs/implementation/future_scope.md`; HLD §8 lists the difference.
- The roadmap's definition of done ("its own `backend/gates/<step>.py`") is met through
  gate 2 for this step only.
