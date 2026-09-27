# Interview UI v1 — reduced proposal after review

**Date:** 2026-09-27. **State:** Recommended scope for review; no UI implementation.

Keep the interview story and evidence quality. Reduce the frontend to three pages,
four presets, and one fixed historical comparison. The [larger design](interview_ui_design.md)
is a reference for possible later work, not a checklist for this version.

## What we would build

| Page | First-version content | Keep simple |
|---|---|---|
| Query & Evidence | Question and explicit cutoff; answer beside actual chunks or facts; source links; expandable L1 trace; exact excerpts sent to Gemini when used | Two columns and expanders; no interactive pipeline canvas |
| Metrics & Evaluations | Read an L1 report; explain Recall@10, MRR, nDCG, exact match, refusals, latency and usage; show failed cases and provisional labels | One selected report, a comparison chart, a case table, short definitions |
| Architecture | Existing HLD, focused retrieval/numbers LLD, simplified schema, key trade-offs and doc links | Static diagrams/images and tabs; no graph editor or node inspector |

The Query page also has a **J&J before/after** tab. Select two curated knowledge cutoffs
for the same fact identity and show the values, source filings, and visibility rule.
This calls a small backend helper around the existing as-of store. It is not a general
time-travel browser and does not depend on parsing that historical period from a question.
Show the fixture's human-review status. Keep later revision information separate from
the evidence eligible for the earlier historical answer.

Four question presets: Apple annual revenue; Apple supply-chain risks; NVIDIA derived
Q4 revenue; JPM gross margin refusal/clarification. The J&J tab is a separate fifth
demonstration. A short written walkthrough replaces a guided-tour engine.

## What we would defer

- React/FastAPI architecture, server endpoint suite, and a separate JavaScript toolchain.
- Data Explorer, arbitrary revision timelines, and a standalone financial dictionary.
- Recorded-run replay engine, custom artifact-version infrastructure, presentation mode,
  elaborate animations, and interactive architecture canvases.
- General growth/series controls, public hosting, authentication, and other product features.

Use a short recorded video as the offline backup. A report read from disk must still
display its capture date and review status; this does not require a query replay system.

## Technology recommendation

Prefer **Streamlit** at the demo step, unless a concrete requirement cannot be met with
its normal layouts. Keep the final framework choice open until that step; do not build
both frameworks. Streamlit supports columns and page navigation and can call the installed
`us_rag` Python package directly. It runs a local server of its own, so the benefit is
avoiding a separate FastAPI service, not eliminating a server entirely.
References: [architecture](https://docs.streamlit.io/develop/concepts/architecture/architecture),
[columns](https://docs.streamlit.io/develop/api-reference/layout/st.columns),
[navigation](https://docs.streamlit.io/develop/api-reference/navigation/st.navigation).

UI code belongs in `frontend/`, even if written in Python. Financial calculations,
data access, source selection, tracing, and model calls remain in `backend/`. The UI
imports public backend functions and opens a read-only connection through backend helpers.
Keep Streamlit dependencies out of backend modules. Preserve the directory separation
requested by the user and recorded in ADR-0022.

Use readable typography, a restrained teal accent, aligned financial figures, generous
spacing, and consistent source cards. Prioritize a polished query/evidence layout over
custom widgets. Check it at normal zoom on the presenter's laptop.

## Work before the demo

1. **Correctness fixes, independently of UI:** repair ratio display and derived citations;
   prevent growth questions receiving plain revenue; reject or deliberately resolve
   mismatched quarter/YTD durations. Add answer-path regression tests, including rendered
   units and citations. Inspect comparison behavior and Q4 input provenance with the DB.
2. **Engineering foundation (E1):** follow the separate CI plan. Fixes can be developed
   alongside E1; GitHub setup should not delay local correctness work.
3. **Observability (L1):** retain actual result evidence, retrieved chunks, submitted
   excerpts, route reason, check outcomes, timings, and available model usage. Export the
   evaluation report. Keep these backend outputs reusable by any future UI.
4. **Demo:** query/evidence first, then evaluations and static architecture, then the
   bounded J&J tab. Capture the video after rehearsing the real scenarios.

Human sign-off runs alongside this work. A provisional report can be displayed as
provisional; it must not be quoted as a validated benchmark. A complete prose judge is
not required to demonstrate existing retrieval/numeric checks; missing metrics stay absent.
No trace/report work is duplicated in the frontend.

## Small release checklist

- [ ] All three pages work; each preset shows real output and actual source evidence.
- [ ] Financial values have correct units and citations; unsupported requests fail clearly.
- [ ] Chunks show filing/section/acceptance time; model excerpts match what was submitted.
- [ ] The evaluation page explains metrics, denominators, failures, and provisional status.
- [ ] HLD/LLD describe the implemented engine and identify limitations.
- [ ] J&J comparison uses one real fact identity and explicit cutoffs with review status.
- [ ] Routine navigation does not rerun models; explicit query submission does. Failures are visible.
- [ ] The laptop walkthrough is rehearsed and a clearly labeled video backup exists.

The next implementation task is backend correctness. This document narrows the UI
proposal; it does not start a frontend build or supersede the shared roadmap.
