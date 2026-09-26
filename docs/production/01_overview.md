# 01 · Overview — problem, users, requirements, scope

## 1. Problem

Answer questions about ten US public companies from their SEC filings, correctly and with
a source for every claim.

A plain "search the documents, let an LLM answer" system is dangerous on financial
filings, for five concrete reasons:

| # | Failure of a naive system | Real example from this corpus |
|---|---|---|
| 1 | **The model does arithmetic** and gets it silently wrong | NVIDIA never files a standalone Q4; it must be computed: 130,497 − 26,044 − 30,040 − 35,082 = 39,331 ($M) |
| 2 | **It uses information from the future** (look-ahead) | A question dated 2024-04-28 must not see Caterpillar's 10-Q accepted 2024-05-01 |
| 3 | **It assumes the past never changes** | JNJ H1 2023 revenue: $50,276M as first reported, $42,413M after the Kenvue restatement |
| 4 | **It computes things that don't exist** | JPMorgan is a bank: it has no "gross profit", so "gross margin" must be refused |
| 5 | **It treats "FY2025" as one calendar period** | Microsoft's FY2025 ends June 2025, Apple's Sep 2025, NVIDIA's Jan 2025 |

## 2. Users

One person in two modes (design §1.1):
- **Trader:** fast fact lookups that are honest about *when* something was known.
- **Researcher:** comparisons across periods and companies, and what filings *say*.

Posture (hard rule): decision support, **not investment advice**. Every answer ends with a
posture line; no recommendations, targets or predictions.

## 3. Scope

**Companies (pin U1):** AAPL, CAT, COST, DE, JNJ, JPM, MSFT, NVDA, WMT, XOM — picked to
stress the system: five different fiscal year-ends, four 52/53-week calendars, a bank
(JPM), a 10-for-1 stock split in the window (NVDA), a restatement (JNJ).

**Time window (pin U2):** each company's own fiscal 2024 and 2025, plus 8-Ks in that span.

**Sources:** SEC EDGAR only — 10-K, 10-Q, 8-K (Item 2.02 earnings releases, Ex-99.1), and
the SEC `companyfacts` XBRL feed. Market prices from Tiingo are designed but **not loaded**
(no API key yet).

**Current corpus:** 389 filings registered (350 downloaded, 39 metadata-only baselines),
41,175 numeric facts, 405 restatement links, 100 fiscal-calendar rows, 7,033 text chunks,
all embedded.

## 4. Functional requirements

| ID | Requirement | Status |
|---|---|---|
| FR1 | Answer single-company metric questions for a fiscal period with an exact number and a citation | Built |
| FR2 | Compare one metric across companies, flagging non-comparable legs | Built |
| FR3 | Derive Q4, YoY, CAGR, margin, TTM in code, with a computation record | Built |
| FR4 | Answer "as of date X" using only what was public at X | Built (numbers and text) |
| FR5 | Return both the as-reported and the restated value of a restated fact, depending on as-of | Built in the store; no dedicated answer template |
| FR6 | Find the filing passages that answer a qualitative question | Built |
| FR7 | Write a prose answer over those passages | Built, **opt-in** (Gemini); off by default |
| FR8 | Refuse, with a reason, questions the data can't answer (CUSIP, intraday price, analyst targets, call Q&A, geo segments, companies outside the 10) | Built |
| FR9 | Ask back when a question is ambiguous (fiscal vs calendar period, basis, mixed coverage) | Built |
| FR10 | Segment figures (e.g. NVIDIA Data Center revenue) as exact numbers | **Deferred** (ADR-0013); answered via text search instead |
| FR11 | Preliminary figures from earnings releases before the 10-Q lands | Extracted, **awaiting human verification**, not loaded |
| FR12 | Split-adjusted price answers | **Not loaded** (no Tiingo key) |

## 5. Non-functional requirements (the hard rules)

These are enforced by code and checked by gates; breaking one fails a gate.

| Rule | Where it's enforced |
|---|---|
| **No LLM arithmetic** — every number comes from SQL or deterministic code | `query/metrics.py`, `query/verify.py`, `backend/gates/phase_04.py` |
| **Point-in-time** — nothing newer than `as_of` is ever read | `store/asof.py`, `query/retrieve.py`, look-ahead checks in gates 3 and 5 |
| **Append-only facts** — corrections are new rows, never edits | DB trigger `facts_append_only`, lint in `backend/gates/phase_01.py` (ADR-0005) |
| **Fiscal periods are looked up, never computed** (U8) | `fiscal.py`, lint in `backend/gates/phase_01.py` |
| **Fail closed** — unknown scale, period, company or mapping → refuse, don't guess | `units.py`, `fiscal.py`, `entities.py`, `metrics.py` |
| **EDGAR fair access** — ≤10 req/s, contact email in User-Agent | `ingest/edgar.py`, `backend/gates/phase_02.py` |
| **Offline checks** — gates never call external data APIs | all `backend/gates/`; CI config |
| **Nothing unverified in the database** — model-extracted figures wait for human sign-off | `ingest/headline.py` (refuses to insert unverified rows) |
| **Read-only answering** — the numbers path runs as a role that cannot write | `usrag_ro` role (`backend/db/migrations/003_metrics.sql`), `db.connect_ro` |

Performance targets are informal: seconds per question on a laptop (8 GB Apple M2). Cost
target: zero (local embeddings, free-tier Gemini — ADR-0008).

## 6. Non-goals

Web API, answer cache, conversation memory, news feeds, embedding fine-tuning, a
multi-step research agent, real-time market data, production hardening, earnings-call
transcripts, CUSIP/ISIN identifiers. Why each is parked and what would bring it back:
`docs/implementation/future_scope.md`.

## 7. Success metrics (the M0 bar)

| Metric | Target | Current (provisional*) |
|---|---|---|
| Quant exact-match on answerable number questions | ≥ 90% | 17/18 = 94% |
| Typed refusal on unanswerable questions | 100% | 100% (10/10) |
| Every emitted number cited | 100% | 100% |
| Look-ahead leaks | 0 | 0 |
| Text-search recall@10 (fused) | ≥ frozen baseline | 0.71 on 26 questions (no baseline frozen yet) |
| Router accuracy | recorded | 60/60 against gate-derived labels |

\* Provisional: the answer key was drafted by the AI and has not been checked by a human.
No number here may be quoted as a result until M0 sign-off
(`docs/implementation/m0_signoff_checklist.md`).
