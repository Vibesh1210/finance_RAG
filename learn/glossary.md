# Glossary — every term in this project, in plain words

Organized by theme. Each entry: what it means, and where it shows up in *our* repo.

---

## Finance & SEC terms

**SEC** — The US government agency that regulates stock markets. Companies that
sell shares to the public must file reports with it.

**EDGAR** — The SEC's public website/database where all those reports live. Free
for anyone, including programs. *Ours:* Phase 2 downloads everything from it.

**Filing** — Any official document a company submits to the SEC.

**10-K** — The big annual report: full-year numbers, business description, risks.
One per year per company.

**10-Q** — The smaller quarterly report. Three per year (the fourth quarter is
covered by the 10-K).

**8-K** — A "something happened" report, filed within days of a notable event:
earnings announced, CEO left, big contract signed.

**Exhibit 99.1 (Ex-99.1)** — The press release attached to an 8-K. When a company
"reports earnings" in the news, this is the actual document. Key fact for us: its
numbers come out **weeks before** the formal 10-Q.

**CIK** — A company's permanent ID number at the SEC (like a passport number).
Tickers change; CIKs don't. *Ours:* the primary key in `companies`.

**Accession number** — A unique ID the SEC stamps on every single filing. *Ours:*
the primary key in `documents`; also how we avoid ingesting anything twice.

**Ticker** — The short stock symbol (NVDA, AAPL). Not permanent! Companies rename
and restructure. *Ours:* the XOM story in DECISIONS.md #4 is a live example.

**XBRL** — Machine-readable tags inside filings. Instead of a program "reading"
the report like a human, each number is labeled: this value is `Revenues`, in
USD, for this exact date range. *Ours:* the source of every number in `facts`.

**iXBRL** — The same tags embedded invisibly inside the normal web-page version
of the filing, so one document serves humans and programs.

**Fiscal year (FY)** — A company's own accounting year, which need not be the
calendar year. Microsoft's runs July–June; NVIDIA's ends in late January.

**FYE** — Fiscal year end. The date the fiscal year closes.

**FY label trap** — A fiscal year is named after the calendar year it *ends* in.
"NVIDIA FY2025" is mostly calendar **2024**. This trips up humans and models
alike, which is why our resolver exists.

**52/53-week calendar** — Some companies end their year on "the last Sunday of
January" instead of a fixed date. Most years have 52 weeks; occasionally one has
53 (and a 14-week quarter). *Ours:* Deere's FY2025 is our in-corpus 53-week case.

**Restatement** — A company officially revising previously reported numbers.
The old number didn't stop having existed — which is exactly why we keep both.

**EPS** — Earnings per share: profit divided by number of shares. Reported in
plain dollars ($6.13), never in millions — why our unit code has "scale-exempt"
classes.

**Basis points (bps)** — Finance's way of saying hundredths of a percent.
350 bps = 3.5% = 0.035.

**Crore/lakh** — Indian number scales (1 crore = 10 million). Only relevant to
the sibling `india_rag/` project; mentioned in docs comparisons.

---

## Time & data concepts (the heart of this system)

**Bitemporal** — "Two kinds of time." Every fact carries (1) the period it
describes and (2) the moment we *learned* it. NVIDIA's Q3 revenue describes
Aug–Oct, but we learned it on Nov 20 (press release), then again on Dec 1
(formal filing). Both times matter.

**Valid time** — Time #1: the period the number is about (`period_start`,
`period_end` in `facts`).

**knowledge_time** — Time #2: when we learned it. *Ours:* the exact timestamp the
SEC accepted the filing.

**As-of query** — Asking "what did we know on date T?" and getting only what was
actually known then. Like reading a newspaper archive from that day, not today's
corrections. *Ours:* `AsOfContext` in `store/asof.py`.

**Point-in-time** — The general principle behind as-of queries: never let
today's knowledge leak into an answer about the past.

**Look-ahead** — The bug this prevents: accidentally using information from the
future ("as of November, revenue was X" — where X was published in December).
In finance research this silently makes strategies look better than they are.

**Append-only** — Rows are only ever added, never changed or deleted. Corrections
are *new* rows. Like an accountant's ledger: you never erase, you add a
correcting entry. *Ours:* enforced by a database trigger on `facts`.

**Supersession** — The link between an old row and the new row that replaces it.
The old row stays (so as-of queries still find it); it just knows its successor.
*Ours:* the `superseded_by` column.

**Preliminary vs final** — The press-release number (preliminary) vs the formal
filing number (final). Usually identical; occasionally not — and the difference
is itself information.

**Provenance** — Where a number came from: which filing, which section, learned
when. Every answer this system ever gives must carry it.

**Security master** — The table-of-record for "what companies exist and what are
they called": IDs, tickers with their validity dates, name aliases.

**Entity resolution** — Turning "Apple", "AAPL", or "Apple Inc." into the same
company record — and *refusing to guess* when a name could mean two companies.

---

## Database terms

**PostgreSQL (postgres)** — The database we store everything in. Runs locally in
a container.

**Schema** — The defined shape of the data: which tables exist, which columns,
what types.

**Migration** — A script that changes the database shape, applied exactly once,
in order. Lets the schema evolve without anyone hand-editing the database.
*Ours:* `db/migrations/001_core.sql`.

**Primary key** — The column that uniquely identifies a row (CIK for companies,
accession for documents).

**Trigger** — Code the *database itself* runs when someone tries an operation.
*Ours:* the one on `facts` that rejects UPDATE/DELETE — so even buggy future
code can't rewrite history.

**Transaction / rollback** — A group of changes that either all happen or none
do. Rolling back throws them away. *Ours:* tests do everything inside a
transaction and roll back, leaving no trace.

**Idempotent** — Safe to run twice; the second run changes nothing. Migrations,
seeds, and ingestion are all built this way, so re-running after a crash is
always safe.

**pgvector** — A postgres add-on that can store and search *embeddings* (see
AI section). Installed now; used from Phase 3.

**Index** — A database structure that makes a particular kind of lookup fast.

**Seed** — Starter rows loaded into a fresh database (our 10 companies, the
hand-entered fiscal calendars).

---

## Engineering process terms

**Gate** — Our per-phase robot checklist (`gates/phase_NN.py`). A phase is
"done" only when its gate script passes. No opinions, just exit codes.

**Regression** — Something that used to work breaking later. `make gates` runs
*every* phase's gate so this is caught immediately.

**CI (continuous integration)** — A server that runs the gates automatically on
every push. Ours is defined in `.github/workflows/ci.yml`.

**Fixture** — A frozen, committed input for tests — like photocopying the phone
book so tests don't depend on the phone company's website being up. *Ours:*
`fixtures/company_tickers.json`.

**Fixtures-only CI** — Our rule that gates never call the live internet. Green
means *our code* is right, not "the internet was up."

**TDD (test-driven)** — Deciding the pass/fail check *before* writing the code.
Our gates are TDD at phase scale.

**Lint** — An automated scan of the source code for forbidden patterns. *Ours:*
the gate greps for quarter-math formulas and for UPDATE/DELETE on facts.

**Fail-closed** — When unsure, refuse loudly instead of guessing quietly. Our
unit parser raises an error on "1,240" with no scale, because guessing risks a
1000× mistake.

**Property test** — Instead of hand-picking examples, a library (hypothesis)
generates hundreds of random inputs and checks a *rule* holds for all of them.
*Ours:* "parsing a rendered quantity always gives back the original."

**One-way door** — A decision that's expensive/impossible to reverse (vs a
two-way door you can walk back through). One-way doors get pinned and written
down; ours is U11.

**Pin (U1–U13)** — A decision we've committed to, numbered, in the execution
plan. Deviating requires a written DECISIONS.md entry.

**Docker / container / docker-compose** — A way to run software (our postgres)
in an isolated box with a pinned version, identical on any machine.

**uv** — The tool managing our Python version and libraries, so every machine
and CI get the exact same environment.

**Rate limiter** — Code that caps how fast we call someone else's server. The
SEC allows max 10 requests/second; ours enforces it unconditionally.

**User-Agent** — A self-identification string sent with web requests. The SEC
requires yours to include a contact email — that's why the gate checks `.env`
for an `@`.

**Decimal vs float** — Two ways computers store numbers. Floats are fast but
approximate (they can silently corrupt huge or precise values); Decimals are
exact. Money code uses Decimal, always.

---

## AI / RAG terms (most arrive in Phases 3–5)

**LLM** — Large language model (Claude is one). In this system the LLM writes
prose and makes choices; it is *never* allowed to do arithmetic or invent
numbers.

**RAG (retrieval-augmented generation)** — Instead of asking an LLM from memory
(it will confabulate), you first *retrieve* the relevant documents/numbers, hand
them over, and have it answer *only from those*. This whole project is a RAG
system with unusually strict rules.

**Corpus** — The document collection we retrieve from: our 10 companies' filings.

**Chunk** — A bite-sized piece of a document (a few paragraphs of one section)
— the unit retrieval works with. *Ours:* the `chunks` table.

**Embedding** — A list of numbers representing a text's *meaning*, so "revenue
grew" and "sales increased" land close together even sharing no words. Stored
in pgvector; ours will come from a model called bge-m3.

**Dense retrieval** — Finding chunks by embedding similarity (meaning-based).

**Sparse / keyword retrieval (BM25-style)** — Finding chunks by matching the
actual words, with clever weighting. Catches exact terms ("Item 1A", "H100")
that meaning-search can miss.

**Hybrid retrieval** — Running both and merging — each covers the other's blind
spots.

**RRF (reciprocal rank fusion)** — The simple recipe for merging two ranked
lists: items ranked high in either list score well.

**Reranker** — A second, slower model that re-scores the top handful of
retrieved chunks for final ordering (Phase 8).

**Router** — The component that classifies each question: numbers question → SQL
path; narrative question → retrieval path; unanswerable → typed refusal
(Phase 5).

**No-LLM-arithmetic** — Our hard rule: every number in an answer is computed by
the database or deterministic code. The LLM narrates; it never calculates.

**Verifier** — The post-check that every number in a drafted answer exactly
matches a retrieved record — a mismatch kills the answer (Phase 4–5).

**Golden questions** — A fixed exam of 60 hand-labeled questions the system is
graded against forever (Phase 3). Written before tuning so we can't
accidentally teach to the test.

## Terms for the post-M0 plan (added 2026-09-18)

**Milestone / M0** — A group of build steps that together give a usable version.
M0 = phases 0–5 = the first working system. M1–M5 were the original later
groups; they've been replaced by the L steps below.

**L1–L5 / Showcase** — The eight remaining steps (`docs/roadmap_learning.md`).
"L" = a learning step that builds a RAG skill; "Showcase" = a step that makes
the project presentable (README, demo page). Numbered in build order.

**[HUMAN]** — A task only you can do (reading a filing, grading an answer,
making a scope call). The build stops and waits when it hits one.

**Provisional vs frozen** — An answer key is *provisional* while it's only the
AI's draft, and *frozen* once you've confirmed it. Scores on a provisional key
prove nothing; scores on a frozen key are the baseline everything is measured
against. M0's key is still provisional.

**Baseline / ratchet** — The first score recorded on the frozen key. "Ratchet
up only" means a later change may never score lower without a written reason.

**Observability** — Being able to see what the system did on each question
from its records alone, without re-running it.

**Trace** — The record one question leaves behind: which lane it took, what
search returned with scores, which SQL ran, what the verifier decided, and
the time, tokens and cost of each step. One file per question (L1).

**Latency** — How long a question takes, usually split per step. "Median" =
the typical case; "p95" = the slow one-in-twenty case.

**Token** — The unit AI models read and write in; roughly three-quarters of a
word. Cost and speed both scale with tokens.

**LLM-as-judge** — Using a second AI model to grade the first one's written
answers. Only trustworthy after you've checked it agrees with your own grades
on a sample (L1 uses ~20 answers).

**Faithfulness** — Does every claim in a written answer come from the sources
it was given? An unsupported claim is a hallucination.

**Relevance** — Did the answer address the question actually asked?

**recall@10 / MRR / nDCG@10** — Three ways to score search. recall@10: of the
right passages, how many are in the top 10. MRR: how high the *first* right
one appears. nDCG@10: are the right ones near the top, not just present.

**Answer-hit@k** — L2's finer score: is the exact answering sentence inside
at least one of the top-k chunks? Stricter than "right section".

**Overlap** — When cutting text into chunks, repeating the last ~100 tokens of
one chunk at the start of the next, so a sentence on the boundary isn't split.

**Cross-encoder** — The reranker's kind of model. An embedding model scores
the question and each chunk separately; a cross-encoder reads them *together*,
which is more accurate and much slower — hence only over the top 20.

**Lift** — The improvement a change produces on the frozen key, e.g. "+0.05
nDCG@10". Always quoted next to its cost (added latency).

**A/B comparison** — Running the system with and without a change on the
same questions, so the only difference in the scores is the change.

**Knowledge graph / GraphRAG** — A map of *things and how they relate*
(Walmart —peer-of→ Costco) instead of passages. Answers "which/how related"
questions that passage search can't. Each link carries its source quote.

**Precision / recall (alerts)** — Precision: of the alerts sent, how many
were worth reading. Recall: of the events worth an alert, how many got one.
A monitor that cries wolf has low precision.

**Watchlist / monitor / dedup** — Watchlist: the companies you want alerts
for. Monitor: the job that checks new filings against it. Dedup: never
alerting twice for the same filing.

**Tiingo** — The free market-data service for daily stock prices. Its key
in `.env` is the one thing missing to load prices.

**Gemini** — The Google model that writes the narrative text of answers.
The only model call in the answer path; it never produces numbers.

**Demo page (Streamlit)** — A single local web page over the system for
showing it working. Not a server, not hosted — the video is what people see.
