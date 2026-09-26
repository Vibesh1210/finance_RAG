# Future scope — parked work

Everything designed or considered but **not** on the roadmap. Nothing here is committed.
Each entry says what it is, why it's parked, and what would bring it back. Reviving one
means an ADR and a roadmap entry.

Original design sections (`§`) are in `archive/design_us.md`; original phases in
`archive/execution_plan_us.md`.

## A. Gaps in what's built (smaller; could be pulled into a step)

| Item | What it is | Why parked | Revive when | Ref |
|---|---|---|---|---|
| **Numeric check on prose** | Extract every number from a model-written answer and verify it against a record; regenerate once, then abstain | Number answers are templated by code, so it wasn't needed for M0 — but Gemini prose is unchecked | Natural fit for L1 (answer grading) | §6.4, HLD §8 |
| **Hybrid route merge** | Run both lanes for mixed questions and combine | M0 sends `hybrid` to text only | A golden question needs both a number and prose | §6.0 |
| **Segment numbers via SQL** | Load business-segment facts from the filings' dimensional XBRL | Needs a new, error-prone extraction pass + human spot-checks | Segment questions need exact numbers, not passages | ADR-0013, §3.2, U10 |
| **U13 for all 10 companies** | Extract press-release figures for the remaining 7 | Free-tier quota ran out after 3 | Before relying on point-in-time preliminary answers | U13 |
| **Price answers** | `price()` template, split-adjusted, NVDA split probe | No Tiingo key | Key added (part of M0 sign-off) | §3.5, §9 probe 3 |
| **"As reported then vs now" template** | One answer showing original and restated values side by side | Store supports it; no answer template | A restatement question in the golden bank | §4.2, phase 8 |
| **LLM router** | Replace rules with a classifier behind `RouteDecision` | Rules scored 60/60 on gate-derived labels | Real questions show misroutes the rules can't fix | ADR-0014 |
| **IR prepared-remarks manifest** | Fetch CFO commentary PDFs/HTML from a curated URL list | Best-effort, non-gating | Narrative answers lack management commentary | U5 |

## B. Cut phases (larger; ADR-0015)

| Item | Original phase | What it is | Why cut | Revive when |
|---|---|---|---|---|
| **Web API + answer cache** | 6 (API half) | FastAPI `/query`, cache keyed by (question, as_of, corpus version), invalidated by restatements | Web engineering, not RAG skill; hosting is a cost trap | A real consumer needs an endpoint |
| **News + prepared remarks** | 7 | Curated RSS with dedup and knowledge time; recency-aware ranking | Low learning density; source licensing | Monitoring (L5) needs news, not just 8-Ks |
| **Conversation memory** | 8 (part) | A frame (company, metric, period, as-of) so "and for Costco?" works | Not RAG-core; adds state | The demo page needs follow-ups |
| **Conflict surfacing** | 8 (part) | Prose like "originally reported X, revised to Y" | Depends on the as-reported template above | Same trigger |
| **Embedder fine-tune + shadow-index drill** | 9 | LoRA fine-tune of bge-m3; build/A-B/cutover/rollback of a second index | Specialised ML side-quest; optional by design | Retrieval plateaus after L2/L3 |
| **Full graph layer** | 10 (beyond POC) | Neo4j, extracted customer/supplier/peer edges | L4 does a POC first | L4 proves graph questions pay off |
| **Multi-hop research agent** | 11 | Planner-executor over retrieve/sql/graph tools with a step budget | Considered again in ADR-0017, not added | Research questions the single-shot path can't answer |
| **Production hardening** | 13 | Stale-filing detection, facts-vs-source reconciliation, backup/restore drill, runbook | Not needed for a local learning project | Anyone else depends on it |

## C. Future direction — LLM-led answering (user, 2026-09-26)

**Intent:** answers should eventually come from an LLM rather than from code templates.
Not being worked on now — the current focus is RAG itself (the L1–L5 roadmap). Two shapes
were discussed:

| | Shape | Fits the no-LLM-arithmetic rule? |
|---|---|---|
| **A** | Relevant chunks + data go into the LLM; the LLM does any maths and writes the final answer | **No.** Reverses the project's core hard rule (a miscalculated number looks exactly like a right one). Needs an ADR superseding the rule, and changes the project story |
| **B** (recommended) | The LLM uses this system as **tools**: it interprets the question ("last 2 years" → FY2024, FY2025), calls `get_metric` / `get_series` / `search_filings` / `compute_change`, then writes the final answer from the tool results | **Yes.** The LLM plans and writes; code fetches and calculates. This is original phase 11's rule: "the agent may request computations, never perform them" |

```
question ─► LLM plans ─► tool calls (exact data, as-of, cited) ─► compute tool (code does maths)
         ─► LLM writes the answer ─► checker: every number matches a tool result, else reject
```

**Building blocks already present:** the engine functions in `query/metrics.py` (would
become tools), `retrieve()` (the search tool), `verify()` (the core of the checker).
**Still needed:** tool wrappers, a numeric checker for LLM-written prose (section A,
first row), and L1's answer grader to measure whether the LLM version is actually better.

**Revive when:** after the L-steps, or earlier if you decide to — via an ADR and a
roadmap entry.

## D. Data never in scope (design decisions, not deferrals)

| Item | Why | Revisit trigger |
|---|---|---|
| Earnings-call transcripts | No regulatory source; vendor transcripts are ToS-restricted | ≥ 5 golden questions need call Q&A (D-US-1) |
| Real-time / intraday prices | Licensed and expensive | — |
| CUSIP / ISIN | Licensed identifiers | — |
| Geographic sub-segments | Scope cut (D-US-3) | Segment questions need geography and curation stays < 2 h |
| Proxy statements (DEF 14A) | Out of v0 (D-US-4) | Governance/compensation questions appear |
| Companies beyond the 10 | Fixed universe (U1) | Deliberate expansion |
