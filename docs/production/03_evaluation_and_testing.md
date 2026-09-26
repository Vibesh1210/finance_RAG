# 03 · Evaluation and testing

Three layers, from fastest to slowest:

```
unit tests (pytest)      pure functions + a throwaway test DB      "does each piece behave?"
phase gates (gates/)     the promises of each build step            "is each step still done?"
golden bank (golden/)    60 + 25 questions with known answers       "is the system any good?"
```

## 1. Unit tests

- `tests/` — 136 test functions in 16 files (units, fiscal, entities, as-of facts, facts
  load, EDGAR client, narrative, headline, prices, metrics, retrieve, router, verify,
  generate, eval, look-ahead). Includes a property test (hypothesis): printing then
  parsing any amount returns the original.
- `tests/conftest.py` drops and rebuilds a database `usrag_test` from the migrations and
  seeds at the start of every session, so every run also tests the migrations. Each test's
  connection rolls back, which keeps tests isolated without breaking the append-only
  trigger.
- Run: `make test`.

## 2. Phase gates

A gate is a plain script, `gates/phase_NN.py`; exit code 0 = pass. It prints a checklist.
`make gate PHASE=N` runs one; `make gates` runs all in order and **stops at the first
red one** (`gates/run_all.py`).

| Gate | Checks | Current |
|---|---|---|
| phase_00 · scaffold | required files present; User-Agent has an email; Postgres + pgvector reachable; `universe.json` byte-identical to its derivation; 10 companies with 10-digit CIKs | green |
| phase_01 · data spine | migrations apply and re-apply; seeds idempotent; lint: no period formulas in `fiscal.py`; lint: no UPDATE/DELETE/TRUNCATE on facts outside `supersede`; live trigger probe; fiscal seed sanity (83–111-day quarters, ADR-0010); canary (NVDA Q3 FY2025 ends 2024-10-27; XOM → predecessor CIK); pytest suite | green |
| phase_02 · ingestion | 1 registry counts · 2 **20 spot-checks [HUMAN]** · 3 fiscal calendars complete, DE FY2025 53-week · 4 section boundaries on 3 filings, Ex-99 chunked · 5 **prices [KEY]** · 6 zero fair-access violations · 7 **U13 rows verified [HUMAN]** · 8 fy/fp independence · 9 **JNJ supersession countersigned [HUMAN]** | 5/9 — the 4 red are human/key items |
| phase_03 · eval + retrieval | bank schema and distribution; leakage lint (no question contains its own answer); **look-ahead: zero future chunks** across all 60 questions, with ≥3 questions that have future chunks to exclude; fused recall ≥ each single leg; **recall ≥ frozen baseline [HUMAN]** | 4/5 — baseline not frozen |
| phase_04 · numbers | registry seeded incl. JPM abstentions; `execution_v0` exact-match 25/25; NVDA Q4 derivation; JPM behaviours; derived values carry a computation record; segment abstains cleanly | green |
| phase_05 · M0 | quant exact-match ≥ 90%; every answered number cited; 100% refusal on unanswerables; clarify questions clarified; zero look-ahead; JPM revenue caveated / gross margin not answered; router accuracy ≥ 0.85 | green (7/7) |

Because `make gates` stops at phase_02, run `make gate PHASE=3`, `4`, `5` directly until
the human items close.

Gate 3 runs the real bge-m3 model (local compute). Gate 5 is model-free: its look-ahead
check uses a constant dummy vector, because the as-of filter doesn't depend on the vector.

## 3. The golden bank

| File | Size | What each question carries | Scored by |
|---|---|---|---|
| `golden/factual_v0.yaml` | 40 | `as_of`, category, expected behaviour, gold passages (accession + section) | recall@10 / MRR / nDCG@10 on the 26 with gold passages; behaviour on the other 14 |
| `golden/quant_v0.yaml` | 20 | `as_of`, gold value + provenance (accession, concept, period_end) | exact match (18 answerable, 2 clarify) |
| `golden/execution_v0.yaml` | 25 | template + parameters → exact value/accession or expected abstention | exact match through the numbers engine |
| `golden/thresholds.yaml` | — | frozen baselines, ratchet-up only | **empty** until sign-off |

Distribution (factual): point-in-time 8, segment 8, cross-company 6, narrative 6, graph 4,
unanswerable 6, fiscal traps 2. Quant: direct metric 12, fiscal traps 8.

**Status: provisional.** Values and passages were drafted by the AI from the loaded data;
a human has not checked them. Quant golds drawn from the same database they grade can only
catch plumbing bugs (the "gold-answer independence rule", design §10.1). The router's
expected routes in gate 5 come from `_expected_route()` in the gate, not from human labels.
Sign-off: `docs/implementation/m0_signoff_checklist.md`.

## 4. Retrieval metrics (`eval/metrics.py`, `eval/harness.py`)

Scored on distinct `(accession, section)` keys in rank order:
- **recall@10** — share of gold passages in the top 10.
- **MRR** — 1 / rank of the first gold passage.
- **nDCG@10** — rewards gold passages ranked higher (binary relevance, log2 discount).

Harness runners: `fused_retriever`, `dense_retriever`, `sparse_retriever`. Ratchet: a
score below a recorded baseline fails gate 3.

Provisional results: fused recall@10 **0.71**, dense 0.63, sparse 0.15 (26 questions).
Weakest categories: cross-company 0.38, narrative 0.67.

## 5. Look-ahead scan (`eval/lookahead.py`)

For each question, run both retrieval legs at its `as_of` across all companies and report
any chunk with `knowledge_time > as_of`. Also counts how many questions have future chunks
to exclude, so the test fails if it ever becomes vacuous. Current: 0 leaks.

## 6. CI (`.github/workflows/ci.yml`)

On every push: Postgres + pgvector service, `uv sync`, enable the extension,
`gates/run_all.py`.

**Known risks (unverified — the repo is private, so run results couldn't be checked from
here):**
- The CI database is empty, so any gate that needs loaded data (2, 3, 4, 5) cannot pass
  there. CI can at most prove gates 0–1.
- `pyyaml` is not a declared dependency; it arrives only through the optional `embed`
  group, which `uv sync` doesn't install by default. Modules that import `yaml`
  (`eval/golden.py`, the registry seed) would fail to import in CI.
- The bge-m3 model is not installed in CI.

Tracked in `docs/implementation/status.md`.

## 7. Not measured yet

- Quality of written (prose) answers — L1 adds an LLM judge, calibrated on ~20
  hand-graded answers.
- Latency and cost per stage — L1.
- Whether the answer *sentence* was retrieved (not just the section) — L2.
