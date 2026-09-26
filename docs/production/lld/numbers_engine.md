# LLD · Numbers engine

`backend/src/us_rag/query/metrics.py`. The deterministic path for every number the system emits.
No model writes SQL or does arithmetic here; results carry a citation or a typed
abstention.

## 1. Lookup pipeline (`metric_value`)

```
(ticker, metric_key, period, as_of)
   │
   ├─ entities.resolve_one(ticker) ────────► company_id           (ambiguous/unknown → error)
   ├─ fiscal.resolve(period) ──────────────► period_start/end     (not in table → abstain: unresolved_period)
   ├─ resolve_mapping(metric, company, as_of)
   │     no row at all ───────────────────► abstain: unmapped_metric
   │     row with us_gaap_tag NULL ────────► abstain: no_comparable_mapping   (e.g. JPM gross_profit)
   ├─ AsOfContext(as_of).facts(company, tag, period_end)
   │     keep: axis IS NULL, unit = mapping.unit
   │     none ─────────────────────────────► abstain: no_data_as_of
   │     prefer period_start match (separates Q4-length rows from the FY row) or instant rows
   │     pick the latest knowledge_time ──► citation precedence (§4.2)
   └─► MetricResult(value, unit, comparable, period_end,
                    citation=[accession · period label · as_of], caveat if not comparable)
```

## 2. The metric registry

`fixtures/metric_mappings.yaml` → table `metric_mappings` (replace-all seed).

**Precedence (`pick_mapping`):** ignore rows with `valid_from > as_of`; a company-specific
row beats the default; among the rest, the latest `valid_from` wins.

| Metric | Default tag | Overrides |
|---|---|---|
| revenue | `Revenues` | AAPL, MSFT, JNJ → `RevenueFromContractWithCustomerExcludingAssessedTax`; JPM `Revenues`, **not comparable** |
| net_income | `NetIncomeLoss` | |
| diluted_eps | `EarningsPerShareDiluted` (USD/shares) | |
| operating_income | `OperatingIncomeLoss` | |
| gross_profit | `GrossProfit` | JPM → **NULL (abstain)** |
| cost_of_revenue | `CostOfGoodsAndServicesSold` | JPM → **NULL (abstain)** |
| operating_cash_flow | `NetCashProvidedByUsedInOperatingActivities` | |
| capital_expenditure | `PaymentsToAcquirePropertyPlantAndEquipment` | |
| total_assets · total_liabilities · stockholders_equity · cash_and_equivalents | `Assets` · `Liabilities` · `StockholdersEquity` · `CashAndCashEquivalentsAtCarryingValue` | |

All rows are `verified_by: "phase4-auto; [HUMAN] pending"` until M0 sign-off.

## 3. Templates

| Function | Returns | Rule |
|---|---|---|
| `metric_value` | `MetricResult \| Abstention` | Section 1 |
| `metric_series(last_n, period_kind)` | `SeriesResult` | Last N calendar rows ending ≤ as_of, each via `metric_value` |
| `metric_compare(tickers)` | `CompareResult` | `comparable` only if every leg resolved AND every mapping is comparable; otherwise a caveat |
| `derived_yoy(fy)` | `DerivedResult` | (FYn − FYn−1) / FYn−1 |
| `derived_cagr(start, end)` | `DerivedResult` | exp(ln(end/start)/years) − 1, in Decimal |
| `derived_margin(period)` | `DerivedResult` | numerator / denominator (default gross_profit / revenue); either abstains → margin abstains |
| `q4_value(fy)` | `Q4Result` | Section 4 |
| `quarter_value(fy, q)` | | Q1–Q3 direct; Q4 via `q4_value` |
| `derived_ttm` | `DerivedResult` | Sum of the last four quarters; additive metrics only |
| `segment_value(member)` | `SegmentResult` | Dimensional rows; abstains `no_segment_data` today (ADR-0013) |

Every `DerivedResult` carries a `computation` string with the exact inputs, e.g.
`(130497000000 - 60922000000) / 60922000000 = 1.142…` — the audit record the verifier
requires.

## 4. Q4 rules

Standalone Q4 is almost never filed (the 10-K reports the full year).

```
q4_value(ticker, metric, FY)
  1. a fact whose period exactly matches the Q4 calendar row (direct, or a press-release row)
        → use it (preliminary flag if source = 8K-EX99)
  2. metric is a balance-sheet (instant) metric
        → Q4-end value = FY-end value
  3. metric is not additive (e.g. diluted EPS)
        → abstain: non_additive   (quarterly EPS doesn't sum: share counts change)
  4. additive metric
        → need FY, Q1, Q2, Q3 all present as of the date, and Q1–Q3 must tile the year
          (start at FY start, back-to-back, end before FY end) — else abstain
        → Q4 = FY − Q1 − Q2 − Q3, source 'derived', cited to the FY filing
```

Additive set: revenue, net_income, operating_income, gross_profit, cost_of_revenue,
operating_cash_flow, capital_expenditure. Instant set: total_assets, total_liabilities,
stockholders_equity, cash_and_equivalents.

Gate example: NVDA Q4 FY2025 revenue = 130,497 − 26,044 − 30,040 − 35,082 = 39,331 ($M).

## 5. Abstention reasons

`unmapped_metric` · `no_comparable_mapping` · `no_data_as_of` · `unresolved_period` ·
`non_additive` · `insufficient_data` · `non_tiling_periods` · `no_calendar` ·
`insufficient_quarters` · `no_segment_data`.

## 6. Safety properties

- Runs under `usrag_ro` (read-only) when the caller passes `db.connect_ro()`.
- All values are `Decimal`; no floats.
- The period is resolved from `fiscal_calendars` only (U8).
- A number is never produced for a NULL mapping: abstention propagates through derived
  values (that is why JPM gross margin abstains).
