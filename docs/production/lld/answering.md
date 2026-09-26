# LLD · Answering: router, answer pipeline, verifier

`query/router.py`, `query/generate.py`, `query/verify.py`.

## 1. Public interface

```python
answer(conn, question: str, *, as_of: date | datetime,
       generate_fn: Callable[[str, list[dict]], str] | None = None) -> Answer

@dataclass
class Answer:
    status: str          # answered | abstained | refused | clarify
    route: str           # metric | narrative | graph | unanswerable | clarify | hybrid
    text: str
    citations: list[str]
    numbers: list        # executor results backing the answer (MetricResult, Q4Result, …)
    reason: str | None   # refusal / abstention reason, or a comparability caveat
```

`as_of` is required. `generate_fn=None` makes no external call; pass
`gemini_generate` for prose.

## 2. Router (`route` → `RouteDecision(route, confidence, tickers, reason)`)

Deterministic (ADR-0014). Entities first, then ordered rules; the first match wins.

```
scan_entities: aliases matched case-insensitively (len ≥ 3); tickers only as UPPERCASE words
               (so the words "de"/"cat" don't match DE/CAT)

1 unanswerable  CUSIP · price target / analyst / intraday / stock price · earnings call / Q&A
                · "in <country>" + a metric word · an out-of-universe company
                (out-of-universe + an in-universe company → clarify instead)
2 narrative     risk / disclose / describe / MD&A / outlook / … (unless "which of" / "trace the" / "relationship between")
3 graph         suppliers / exposed to / concentration among / customers of / relationship between
4 clarify       "Q# YYYY" without FY · two companies + a quarter · "in YYYY" + metric without fiscal/FY
                · gross margin/profit with JPM · metric + company but no period
5 narrative     segment words (data center, intelligent cloud, …) → text lane (ADR-0013)
                · "as of" / "announced" → press-release text
6 metric        metric words + a company
7 hybrid        anything else (confidence 0.5)
```

## 3. `answer()` dispatch

```
route ─┬─ unanswerable | graph ──► Answer("refused", reason)
       ├─ clarify ───────────────► Answer("clarify", "That's ambiguous: … Could you specify?")
       ├─ metric ────────────────► _metric_answer
       └─ narrative | hybrid ────► _narrative_answer          (hybrid does NOT run the metric lane)
```

### Metric lane (`_metric_answer`)

```
extract_metric_key  keyword table, longest phrases first ("total net sales" → revenue, "eps" → diluted_eps)
extract_period      regex: "Q3 FY2025", "third quarter 2024", "FY2025", "fiscal year 2025", "ended June 30, 2025"
missing any of metric / period / company → abstained

2+ companies → metric_compare → per-leg verify → "Revenue for FY2025 — AAPL $…; MSFT $… (caveat)"
gross_margin → derived_margin
period Q4    → q4_value
otherwise    → metric_value
Abstention   → Answer("abstained", "I can't provide that: <detail>")
verify fails → Answer("abstained")
else         → "{TICKER}'s {metric} for {period} was ${N} million (caveat) [citation]. <posture>"
```

Formatting: USD values as whole millions (`$416,161 million`); per-share values as
`$7.46 per share`.

### Text lane (`_narrative_answer`)

```
retrieve(question, as_of, top_k=8, company_ids from router)
no hits          → abstained
generate_fn None → "Relevant disclosure is in <section> of <accession>, … (as of …). <posture>"
generate_fn set  → generate_fn(question, top-6 passages) + posture
citations        → top-3 "[accession · section]"
```

`gemini_generate`: `GEMINI_MODEL` (default `gemini-2.5-flash-lite`), passages truncated to
1,500 characters each, prompt: use only the passages, cite, say so if they don't answer,
state no number that isn't verbatim in a passage.

## 4. Verifier (`verify(result, claimed_value, claimed_accession, claimed_comparable)`)

| Check | Fails when |
|---|---|
| Abstention guard | a number is claimed for an `Abstention` |
| Type guard | the result isn't a value-bearing result type |
| No-LLM-arithmetic | a `DerivedResult` / derived `Q4Result` has no computation record |
| Exact match | the claim ≠ the source, and ≠ the source rounded to the claim's own decimal places ("0.47" for 0.4690… passes) |
| Citation precedence | the claimed accession ≠ the authoritative one |
| Comparability | comparability is claimed for a non-comparable result |

**How it is used today:** `_metric_answer` calls `verify(res, claimed_value=res.value)`,
i.e. the executor's value against itself — so in practice it guards type and the
computation record. The designed use (extract every number from a model-written draft,
verify each, regenerate once, then abstain) is not built, because number answers are
templated by code. **Numbers inside Gemini prose are not verified** — see HLD §8.

## 5. Posture

Every `answered` text ends with: *"This is sourced information for decision support, not
investment advice."* Refusals and clarifications don't.
