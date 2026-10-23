# I1 — Ingestion quality: fixing section boundaries

**Status:** done 2026-10-23 (branch `i1/ingestion-quality`, merged by pull request) · started 2026-09-27

> **Read this first.** Sections 1–5 explain in plain words what's wrong and what we're
> doing about it. Section 6 is filled in as the work happens — come back to it for what I
> actually found.

---

## 1. What "ingestion" does to a filing's text — the flow

An annual report (10-K) is one long web page. To make it searchable, the system cuts it
up in three steps:

```
  10-K web page ──► 1 FIND HEADINGS ──► 2 CUT INTO SECTIONS ──► 3 CUT SECTIONS INTO CHUNKS ──► embed + store
                    "Item 1A", "Item 7",   everything between     ~a page each, never           each chunk keeps
                    "Item 7A", "Item 8" …  two headings is one     crossing into another         its SECTION LABEL
                                           section                 section
```

We keep four sections of every 10-K:

| Label | What it is | Typical size |
|---|---|---|
| Item 1 | What the business does | ~20 chunks |
| Item 1A | Risk factors | ~30 chunks |
| Item 7 | Management's discussion of the results (MD&A) | ~30 chunks |
| Item 7A | Market risk (interest rates, currencies…) | **~2 chunks** — usually 1–3 pages |

The **section label matters twice**:
1. **Search** can filter by it ("only risk factors").
2. **The test questions grade by it**: a test question says "the answer is in Deere's
   10-K, **Item 7**". A found chunk counts as a hit only if its label matches.

## 2. What went wrong

A section runs from its heading **until the next heading we recognise**. For Item 7A,
the next heading is "Item 8" (the financial statements). In JPMorgan's and Deere's
annual reports, "Item 8" was **not recognised** — so Item 7A never stopped:

```
  normal 10-K:   … │ Item 7 (MD&A) │ Item 7A ▌2 chunks▐ │ Item 8 … (not kept) │
                                                      ▲ stops here

  JPM / DE:      … │ Item 7 (MD&A) │ Item 7A ▌████████████████████████████████████▐ end of document
                                               ~105 chunks: controls, disclaimers, and possibly
                                               the real MD&A — all labelled "market risk"
```

Measured on 2026-09-27: 4 filings × ~105 chunks ≈ **420 chunks with the wrong label —
6% of the whole search index**.

## 3. Why it matters

- **Search quality:** a question about market risk gets pages of unrelated text; a
  question about JPMorgan's business results may find the right text under the wrong label.
- **Scores could be unfair:** test questions F14 (Deere) and F15 (JPMorgan) expect "Item 7".
  If their answers sat under the wrong "Item 7A" label, search would find them but grade
  them as misses. *(Checked before the rebuild: both already scored 1.0 — the right "Item 7"
  chunks were found anyway. So the harm was noise and wrong labels, not these two scores.)*
- **Timing:** your sign-off freezes the score baselines. Fixing chunks *after* the freeze
  would mean re-baselining. So fix first.

## 4. How we fix it — the plan

```
 1 INVESTIGATE        open the JPM and DE filings, see how their "Item 8" heading is written,
                      and why the heading-finder skipped it                 (root cause, no guessing)
 2 FAILING TEST       a small test built from that exact heading style — it must FAIL today
 3 FIX                change the heading-finder so the test passes — and all old tests still pass
 4 GUARD              an automatic check over ALL 80 annual/quarterly reports: flag any section
                      far bigger than normal for its type          (would have caught this on day one)
 5 RE-CHUNK           delete + rebuild the chunks of ONLY the affected filings, re-embed them
                      (~minutes, not hours); everything else untouched
 6 RE-MEASURE         re-run the gates and the search scores; compare before/after
 7 ITEM 8 DECISION    financial-statement notes are never extracted today — add, or record why not
```

A note on step 5: chunks are rebuilt, but **nothing in the numbers database changes** —
this is only about the text side. The "never erase" rule applies to *facts* (numbers);
text chunks are derived from files on disk and can always be rebuilt.

## 5. Words you'll meet

- **Heading detection** — the code that looks at each line of the filing and decides
  "this is the start of Item 8". It uses patterns, so an unusual layout can fool it.
- **Table of contents trap** — every 10-K lists "Item 8 … page 52" in its contents page.
  The heading-finder must skip those lines, or every section would end on page 2. That
  skipping is a likely suspect here.
- **Re-embed** — turning the rebuilt chunks into meaning-vectors again (bge-m3), so the
  search index matches the new text.
- **Regression test** — a test that pins a bug: it fails while the bug exists and keeps the
  bug from ever coming back.

---

## 6. What I found and did (filled in as the work happens)

### 6.1 Root cause — it wasn't the "Item 8" heading after all

JPMorgan and Deere don't put their MD&A and market-risk text under "Item 7 / Item 7A"
headings. Their Item list only says *"see page 46"*. So a **fallback** finds the sections
by their **caption** instead — e.g. the words "Management's discussion and analysis" — and
cuts until a "stop" caption like "Report of Independent Registered Public Accounting Firm".

That fallback had **three weaknesses**, and the two companies each hit different ones:

```
 1 IT TRUSTED CONTENTS PAGES    A caption that is really a row in a table of contents
                                ("Management's discussion and analysis: | Introduction | 46")
                                or a page index ("Market Risk | 133-142") was taken as the
                                START of a section.                         → JPM, XOM
 2 IT DIDN'T KNOW DEERE'S WORDS  Deere's statements are titled "STATEMENTS OF CONSOLIDATED
                                INCOME"; the stop pattern only knew "Consolidated statements
                                of income". No stop sign → run to the end of the document. → DE
 3 IT IGNORED HEADINGS IT KNEW   The normal pass had already found "ITEM 8." right after
                                Deere's one-paragraph Item 7A — the fallback never checked. → DE
```

What that did to the data (measured, all 80 annual/quarterly reports compared):

| Filing | Before | After |
|---|---|---|
| Deere 10-K ×2 | MD&A 101 chunks *and* "7A" 104 — the **same text twice** (both ran to the end, incl. financial statements) | MD&A 29 chunks, ends right before the statements; no separate 7A (Deere's 7A is a one-paragraph pointer to the MD&A) |
| JPMorgan 10-K ×2 | MD&A 53 (started in the contents page) + "7A" 108 (started at an index row, held the back half of the MD&A) | the whole MD&A, 158 chunks, from its real start to the auditor's report; no separate 7A (JPM's market risk is a subsection *inside* its MD&A) |
| JPMorgan 10-Q ×6 | MD&A cut off early (31–45 chunks) at a "Market Risk" index row | full MD&A (88–109) |
| ExxonMobil 10-K 2026 | MD&A opened with a contents list | starts at the real "FORWARD-LOOKING STATEMENTS" |
| the other 69 | — | unchanged |

### 6.2 The fix (3 rules, no company special-cases) — `backend/src/us_rag/ingest/narrative.py`

1. **A caption doesn't count if it's a contents/index row** — one of the next two lines is a
   link or a page number ("46", "133-142").
2. **A caption section also stops at the next "Item" heading already found.**
3. **The stop pattern knows "Statements of consolidated income"** and a trailing full stop.

Proved by 3 new tests that rebuild each company's layout in miniature (JPM, DE, XOM shapes) —
each failed before the fix and passes after. All 139+ tests green.

One wrong turn, kept here because it teaches something: my first version looked only **one**
line ahead for rule 1. It fixed Deere and JPM but *moved* ExxonMobil's contents list into its
2025 MD&A — the 80-filing comparison caught it, a faithful miniature reproduced it, and looking
two lines ahead fixed it. **Always compare every filing, not just the ones you meant to fix.**

### 6.3 The guard — so it can't hide again

`backend/src/us_rag/ingest/section_audit.py` + gate 2 check **4b** audit *every* stored filing
for the three shapes this bug took: **overlapping sections**, **market risk bigger than the
MD&A**, **a section opening with a contents list**. (Plain "too big" isn't a rule: JPM's MD&A
is genuinely long.) On the old data it **fails with 11 problems** — exactly the filings above.

### 6.4 Rebuild + before/after (2026-09-28)

**Rebuild:** the 11 changed filings' chunks were backed up (1,321 rows, text + vectors, so it
can be undone), deleted, re-chunked and re-embedded → 1,325 new chunks; index 7,033 → 7,037.
Every changed section matched the prediction exactly; no other section moved.

**Guard:** gate 2 check 4b went from **11 problems → PASS**. Gates 2, 3, 5 otherwise unchanged
(2 and 3 red only on your sign-off items; gate 5 7/7; zero look-ahead leaks).

**Search scores (provisional answer key, 26 questions):**

| | recall@10 before → after | MRR | nDCG@10 |
|---|---|---|---|
| fused | 0.7115 → **0.6731** | 0.4106 → 0.4010 | 0.4771 → 0.4605 |
| dense | 0.6346 → 0.6346 | 0.3345 → 0.3346 | 0.3900 → 0.3900 |
| keyword | 0.1538 → 0.1154 | 0.1538 → 0.1154 | 0.1538 → 0.1154 |

The whole drop is **one question, F14** ("What did Deere report for its Production and
Precision Agriculture segment in fiscal 2025?"), 1.0 → 0.0. Why:

```
BEFORE  Deere's "Item 7" = MD&A + the financial statements + notes (mislabelled)
        → segment tables from the NOTES matched the question, labelled "Item 7" → counted as a hit
AFTER   Deere's "Item 7" = only the real MD&A
        → search now ranks higher Deere's Q4 FY2025 earnings press release and call slides
          (8-K EX-99.1 / EX-99.2, "Production & Precision Ag", full-year results) — arguably
          the better source — but F14's answer key accepts ONLY the 10-K Item 7 → counted as misses
```

So the measurement became **more honest**, not the system worse: the old hit came from
mislabelled text, and F14's answer key is too narrow. **Not changed here** — correcting an
answer key is your sign-off call; flagged in `../m0_signoff_checklist.md` Part 5.

**Two lessons worth keeping:**
1. *A bug can inflate a score.* Fixing data can lower a number that was never real.
2. *Press releases compete with the filings.* 41% of all chunks are 8-K exhibits; for F14 the
   top 9 results are press releases and earnings slides. Whether that's good (they're direct,
   dated answers) or bad (they crowd out the 10-K) is a question for L2 (chunking) and L3
   (reranker) — and for how many acceptable passages each test question should list.

### 6.5 Item 8 decision (2026-10-23) — not now, written down

Measured over the cached 10-Ks: the 14 whose "Item 8" the heading pass finds would add
**665 chunks** (+34% on the 1,942 kept from 10-Ks). DE, JPM and NVDA would need new
caption-located extraction, the same kind of code this step just had to fix. With the
10-Q statements, about **2,500 chunks, +35% of the index**. No test question points to
Item 8.

You chose **not now**: the statement tables are numbers the numbers lane already owns,
and a +35% index right before the baseline freeze would move every score with nothing to
justify it. Recorded in **ADR-0023**, listed in `future_scope.md`, to be measured in L2.

### 6.6 Done — checked 2026-10-23
- `make check`: lint clean, 107 unit tests; 37 integration tests (144 total).
- Gate 2: check 4b PASS; red only on the 4 human/key items (spot-checks, prices, U13,
  JNJ countersign). Gates 0, 1, 4, 5 green; gate 3 red only on human items.
- Ingestion LLD §4 now describes the caption fallback, its three I1 rules, and the audit;
  HLD §8 lists the Item 8 difference; roadmap lists I1.
