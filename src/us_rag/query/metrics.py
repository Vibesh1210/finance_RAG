"""Phase 4 SQL branch (design §6.2): the deterministic, provenance-carrying metric path.

The LLM never writes SQL and never does arithmetic. It selects a template and binds
parameters (entity, metric_key, period); the registry (`metric_mappings`) resolves the
metric to a reviewed us-gaap tag, and a read-only executor fetches the exact value with
bitemporal as-of correctness (`store.asof`) and a citation. An unmapped metric — or a
company with an explicit NULL mapping (e.g. a bank's gross profit) — returns a typed
ABSTENTION, never a computed guess.

This slice is the `metric_value` spine; series / compare / derived / segment and Q4
derivation build on the same resolver (later Phase 4 slices).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg

from us_rag.entities import resolve_one
from us_rag.env import repo_root
from us_rag.fiscal import resolve as resolve_period
from us_rag.store.asof import AsOfContext

REGISTRY_FILE = repo_root() / "fixtures" / "metric_mappings.yaml"


# ---------- registry ----------


@dataclass(frozen=True)
class Mapping:
    metric_key: str
    company_id: int | None
    us_gaap_tag: str | None  # None = explicit typed abstention
    unit: str
    comparable: bool
    provenance: str | None
    valid_from: date | None


def pick_mapping(rows: list[Mapping], as_of: date) -> Mapping | None:
    """Pure resolver precedence: a company-specific row beats the default; respect
    `valid_from` (ignore rows not yet in effect); the latest in-effect row wins. Returns
    the chosen Mapping (which may itself be an abstention, us_gaap_tag=None) or None when
    no row applies at all (unknown metric)."""
    applicable = [m for m in rows if m.valid_from is None or m.valid_from <= as_of]
    if not applicable:
        return None
    applicable.sort(key=lambda m: (m.company_id is not None, m.valid_from or date.min))
    return applicable[-1]


def resolve_mapping(
    conn: psycopg.Connection, metric_key: str, company_id: int, as_of: date
) -> Mapping | None:
    rows = [
        Mapping(*row)
        for row in conn.execute(
            "SELECT metric_key, company_id, us_gaap_tag, unit, comparable, provenance, valid_from"
            " FROM metric_mappings WHERE metric_key = %s AND (company_id = %s OR company_id IS NULL)",
            (metric_key, company_id),
        ).fetchall()
    ]
    return pick_mapping(rows, as_of)


def seed_metric_mappings(conn: psycopg.Connection, path: Path | None = None) -> int:
    """Load the reviewed registry from YAML. Idempotent replace-all — this is config,
    not append-only facts (so DELETE is fine; the append-only rule guards `facts` only)."""
    import yaml

    entries = yaml.safe_load((path or REGISTRY_FILE).read_text()) or []
    conn.execute("DELETE FROM metric_mappings")  # config table; not the `facts` spine
    for e in entries:
        company_id = resolve_one(conn, e["company"]).company_id if e.get("company") else None
        conn.execute(
            "INSERT INTO metric_mappings (metric_key, company_id, us_gaap_tag, unit,"
            " comparable, provenance, verified_by, valid_from) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (e["metric_key"], company_id, e.get("us_gaap_tag"), e["unit"],
             e.get("comparable", True), e.get("provenance"), e.get("verified_by"),
             e.get("valid_from")),
        )
    conn.commit()
    return len(entries)


# ---------- results ----------


@dataclass(frozen=True)
class Citation:
    accession: str
    period: str
    as_of: date


@dataclass(frozen=True)
class MetricResult:
    metric_key: str
    ticker: str
    value: Decimal
    unit: str
    comparable: bool
    period_end: date
    citation: Citation
    caveat: str | None = None


@dataclass(frozen=True)
class Abstention:
    metric_key: str
    ticker: str
    reason: str  # unmapped_metric | no_comparable_mapping | no_data_as_of | unresolved_period
    detail: str


def _to_dt(as_of: date | datetime) -> datetime:
    if isinstance(as_of, datetime):
        return as_of
    return datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)


def _period_label(fr) -> str:
    return f"FY{fr.fiscal_year}" if fr.fiscal_period == "FY" else f"{fr.fiscal_period} FY{fr.fiscal_year}"


def metric_value(
    conn: psycopg.Connection, ticker: str, metric_key: str, period: str, *, as_of: date | datetime
) -> MetricResult | Abstention:
    """Look up ONE exact number, point-in-time-correct, with a citation — or abstain.

    `as_of` is required (every read is point-in-time). Pass a read-only connection
    (`db.connect_ro`) to run under the read-only executor role."""
    as_of_dt = _to_dt(as_of)
    as_of_date = as_of_dt.date()
    company = resolve_one(conn, ticker)
    try:
        fr = resolve_period(conn, company.company_id, ticker, period)
    except Exception as exc:  # unknown/unseeded period
        return Abstention(metric_key, ticker, "unresolved_period", str(exc))

    mapping = resolve_mapping(conn, metric_key, company.company_id, as_of_date)
    if mapping is None:
        return Abstention(metric_key, ticker, "unmapped_metric", f"no mapping for {metric_key!r}")
    if mapping.us_gaap_tag is None:
        return Abstention(
            metric_key, ticker, "no_comparable_mapping",
            mapping.provenance or f"{metric_key} does not apply to {ticker}",
        )

    facts = AsOfContext(conn, as_of_dt).facts(
        company_id=company.company_id, concept=mapping.us_gaap_tag, period_end=fr.period_end
    )
    # company-level (not a segment member) rows in the mapping's unit
    rows = [f for f in facts if f.get("axis") is None and f["unit"] == mapping.unit]
    if not rows:
        return Abstention(
            metric_key, ticker, "no_data_as_of",
            f"no {mapping.us_gaap_tag} for {ticker} {_period_label(fr)} as of {as_of_date}",
        )
    # A Q4-duration fact shares its period_end with the full year; disambiguate by
    # period_start (instant/balance-sheet facts carry none). Fall back if the stored
    # start doesn't line up with the calendar, so this can never drop a valid FY row.
    exact = [f for f in rows if f["period_start"] == fr.period_start or f["period_kind"] == "instant"]
    rows = exact or rows
    # citation precedence (§4.2): the latest authoritative row known by as_of
    row = max(rows, key=lambda f: f["knowledge_time"])
    caveat = None if mapping.comparable else (mapping.provenance or "not comparable across companies")
    return MetricResult(
        metric_key=metric_key, ticker=ticker, value=row["value"], unit=mapping.unit,
        comparable=mapping.comparable, period_end=fr.period_end,
        citation=Citation(row["accession"], _period_label(fr), as_of_date), caveat=caveat,
    )


# ---------- series & compare (same lookup, many periods / many companies) ----------


@dataclass(frozen=True)
class SeriesResult:
    metric_key: str
    ticker: str
    points: list[MetricResult | Abstention]


def metric_series(
    conn: psycopg.Connection, ticker: str, metric_key: str, *,
    last_n: int, as_of: date | datetime, period_kind: str = "FY",
) -> SeriesResult:
    """The last `last_n` fiscal periods of a metric, newest first — each looked up
    through metric_value (so each point is as-of-correct, cited, or abstains)."""
    as_of_date = _to_dt(as_of).date()
    company = resolve_one(conn, ticker)
    rows = conn.execute(
        "SELECT fiscal_year, fiscal_period FROM fiscal_calendars"
        " WHERE company_id = %s AND fiscal_period = %s AND period_end <= %s"
        " ORDER BY period_end DESC LIMIT %s",
        (company.company_id, period_kind, as_of_date, last_n),
    ).fetchall()
    points = [
        metric_value(conn, ticker, metric_key, _label(fy, fp), as_of=as_of) for fy, fp in rows
    ]
    return SeriesResult(metric_key, ticker, points)


@dataclass(frozen=True)
class CompareResult:
    metric_key: str
    period: str
    results: list[MetricResult | Abstention]
    comparable: bool
    caveat: str | None


def metric_compare(
    conn: psycopg.Connection, tickers: list[str], metric_key: str, period: str, *,
    as_of: date | datetime,
) -> CompareResult:
    """The same metric across companies for one period. `comparable` is true only if every
    leg resolved AND every mapping is comparable (design §6.4 comparability enforcement)."""
    results = [metric_value(conn, t, metric_key, period, as_of=as_of) for t in tickers]
    resolved = [r for r in results if isinstance(r, MetricResult)]
    comparable = len(resolved) == len(tickers) and all(r.comparable for r in resolved)
    caveat = None if comparable else "comparison has non-comparable or abstaining legs — interpret with care"
    return CompareResult(metric_key, period, results, comparable, caveat)


def _label(fiscal_year: int, fiscal_period: str) -> str:
    return f"FY{fiscal_year}" if fiscal_period == "FY" else f"{fiscal_period} FY{fiscal_year}"


# ---------- derived metrics: computed in code, never by the LLM (no-arithmetic rule) ----------


@dataclass(frozen=True)
class DerivedResult:
    kind: str  # 'YoY' | 'CAGR' | 'margin'
    ticker: str
    label: str
    value: Decimal
    unit: str  # 'ratio' for growth/margin
    computation: str  # the exact formula with inputs — the audit record (design §6.4)
    inputs: list[MetricResult]
    caveat: str | None = None


def _pct_change(cur: Decimal, prev: Decimal) -> Decimal:
    return (cur - prev) / prev


def _ratio(num: Decimal, den: Decimal) -> Decimal:
    return num / den


def _cagr(start: Decimal, end: Decimal, years: int) -> Decimal:
    # geometric growth via Decimal ln/exp — deterministic, high precision
    return ((end / start).ln() / Decimal(years)).exp() - Decimal(1)


def _first_abstention(*results):
    for r in results:
        if isinstance(r, Abstention):
            return r
    return None


def _combine_caveats(*results: MetricResult) -> str | None:
    caveats = [r.caveat for r in results if r.caveat]
    return "; ".join(caveats) or None


def derived_yoy(
    conn: psycopg.Connection, ticker: str, metric_key: str, fiscal_year: int, *,
    as_of: date | datetime,
) -> DerivedResult | Abstention:
    """Year-over-year change of a metric: (FYn - FYn-1) / FYn-1."""
    cur = metric_value(conn, ticker, metric_key, f"FY{fiscal_year}", as_of=as_of)
    prev = metric_value(conn, ticker, metric_key, f"FY{fiscal_year - 1}", as_of=as_of)
    if (ab := _first_abstention(cur, prev)):
        return Abstention(f"{metric_key}_yoy", ticker, ab.reason, f"{ab.metric_key}: {ab.detail}")
    value = _pct_change(cur.value, prev.value)
    return DerivedResult(
        "YoY", ticker, f"{metric_key} YoY FY{fiscal_year}", value, "ratio",
        f"({cur.value} - {prev.value}) / {prev.value} = {value}", [prev, cur],
        _combine_caveats(cur, prev),
    )


def derived_cagr(
    conn: psycopg.Connection, ticker: str, metric_key: str, start_year: int, end_year: int, *,
    as_of: date | datetime,
) -> DerivedResult | Abstention:
    """Compound annual growth rate of a metric between two fiscal years."""
    start = metric_value(conn, ticker, metric_key, f"FY{start_year}", as_of=as_of)
    end = metric_value(conn, ticker, metric_key, f"FY{end_year}", as_of=as_of)
    if (ab := _first_abstention(start, end)):
        return Abstention(f"{metric_key}_cagr", ticker, ab.reason, f"{ab.metric_key}: {ab.detail}")
    years = end_year - start_year
    value = _cagr(start.value, end.value, years)
    return DerivedResult(
        "CAGR", ticker, f"{metric_key} CAGR FY{start_year}->FY{end_year}", value, "ratio",
        f"({end.value}/{start.value})^(1/{years}) - 1 = {value}", [start, end],
        _combine_caveats(start, end),
    )


def derived_margin(
    conn: psycopg.Connection, ticker: str, period: str, *, as_of: date | datetime,
    numerator: str = "gross_profit", denominator: str = "revenue", name: str = "gross_margin",
) -> DerivedResult | Abstention:
    """A margin ratio (numerator / denominator) for one period. If either underlying metric
    abstains, the margin abstains — this is why JPMorgan gross margin abstains, not computes."""
    num = metric_value(conn, ticker, numerator, period, as_of=as_of)
    den = metric_value(conn, ticker, denominator, period, as_of=as_of)
    if (ab := _first_abstention(num, den)):
        return Abstention(name, ticker, ab.reason, f"{ab.metric_key}: {ab.detail}")
    value = _ratio(num.value, den.value)
    return DerivedResult(
        "margin", ticker, f"{name} {period}", value, "ratio",
        f"{num.value} / {den.value} = {value}", [num, den], _combine_caveats(num, den),
    )


# ---------- Q4 derivation & TTM (design §6.2 — the pinned quarterly rules) ----------

# Additive flow metrics may be derived by subtraction (Q4 = FY - Q1 - Q2 - Q3).
ADDITIVE = frozenset({
    "revenue", "net_income", "operating_income", "gross_profit",
    "cost_of_revenue", "operating_cash_flow", "capital_expenditure",
})
# Balance-sheet metrics: the Q4-end value IS the FY-end value.
INSTANT = frozenset({"total_assets", "total_liabilities", "stockholders_equity", "cash_and_equivalents"})


@dataclass(frozen=True)
class Q4Result:
    ticker: str
    metric_key: str
    fiscal_year: int
    value: Decimal
    unit: str
    source: str  # 'derived' | 'instant' | '8K-EX99' | '10-Q'/'10-K'
    preliminary: bool
    derived: bool
    citation: Citation
    computation: str | None
    caveat: str | None = None


def _q4_derive(fy: Decimal, q1: Decimal, q2: Decimal, q3: Decimal) -> Decimal:
    return fy - q1 - q2 - q3


def periods_contiguous(fy_start: date, fy_end: date, quarters: list[tuple[date, date]]) -> bool:
    """Q1..Q3 must start at the fiscal-year start, be back-to-back with no gaps, and end
    strictly before the year end (so the derived Q4 remainder is a real, non-empty period)."""
    qs = sorted(quarters)
    if qs[0][0] != fy_start:
        return False
    for (_, end0), (start1, _) in zip(qs, qs[1:]):
        if (start1 - end0).days != 1:
            return False
    return qs[-1][1] < fy_end


def q4_value(
    conn: psycopg.Connection, ticker: str, metric_key: str, fiscal_year: int, *,
    as_of: date | datetime,
) -> Q4Result | Abstention:
    """Standalone Q4 of a metric (design §6.2). Precedence: a directly-reported or U13
    preliminary Q4 row known as-of → then balance-sheet = FY-end → then additive
    derivation FY - Q1 - Q2 - Q3 → else abstain. Non-additive (EPS) is never subtracted."""
    as_of_dt = _to_dt(as_of)
    as_of_date = as_of_dt.date()
    company = resolve_one(conn, ticker)
    mapping = resolve_mapping(conn, metric_key, company.company_id, as_of_date)
    if mapping is None:
        return Abstention(f"{metric_key}_q4", ticker, "unmapped_metric", f"no mapping for {metric_key!r}")
    if mapping.us_gaap_tag is None:
        return Abstention(f"{metric_key}_q4", ticker, "no_comparable_mapping",
                          mapping.provenance or f"{metric_key} does not apply to {ticker}")
    fr_q4 = resolve_period(conn, company.company_id, ticker, f"Q4 FY{fiscal_year}")

    # 1) a directly-reported or U13-preliminary Q4 fact known as-of (period_start marks it Q4)
    q4_facts = [
        f for f in AsOfContext(conn, as_of_dt).facts(
            company_id=company.company_id, concept=mapping.us_gaap_tag, period_end=fr_q4.period_end)
        if f["axis"] is None and f["unit"] == mapping.unit and f["period_start"] == fr_q4.period_start
    ]
    if q4_facts:
        row = max(q4_facts, key=lambda f: f["knowledge_time"])
        preliminary = bool(row["preliminary"]) or row["source"] == "8K-EX99"
        return Q4Result(
            ticker, metric_key, fiscal_year, row["value"], mapping.unit, row["source"], preliminary,
            False, Citation(row["accession"], f"Q4 FY{fiscal_year}", as_of_date), None,
            None if mapping.comparable else mapping.provenance,
        )

    # 2) instant (balance-sheet) metric: the Q4-end value is the FY-end value
    if metric_key in INSTANT:
        fy = metric_value(conn, ticker, metric_key, f"FY{fiscal_year}", as_of=as_of)
        if isinstance(fy, Abstention):
            return fy
        return Q4Result(ticker, metric_key, fiscal_year, fy.value, fy.unit, "instant", False, False,
                        fy.citation, "FY-end balance = Q4-end balance", fy.caveat)

    # 3) non-additive (e.g. EPS): never derive by subtraction
    if metric_key not in ADDITIVE:
        return Abstention(f"{metric_key}_q4", ticker, "non_additive",
                          f"Q4 {metric_key} is not derivable by subtraction; needs a preliminary/U13 row")

    # 4) additive derivation: Q4 = FY - Q1 - Q2 - Q3, guarded by a period-tiling check
    fy = metric_value(conn, ticker, metric_key, f"FY{fiscal_year}", as_of=as_of)
    q1 = metric_value(conn, ticker, metric_key, f"Q1 FY{fiscal_year}", as_of=as_of)
    q2 = metric_value(conn, ticker, metric_key, f"Q2 FY{fiscal_year}", as_of=as_of)
    q3 = metric_value(conn, ticker, metric_key, f"Q3 FY{fiscal_year}", as_of=as_of)
    if (ab := _first_abstention(fy, q1, q2, q3)):
        return Abstention(f"{metric_key}_q4", ticker, "insufficient_data",
                          f"cannot derive Q4 — {ab.metric_key} {ab.reason} as of {as_of_date}")
    prows = conn.execute(
        "SELECT fiscal_period, period_start, period_end FROM fiscal_calendars"
        " WHERE company_id = %s AND fiscal_year = %s AND fiscal_period IN ('Q1','Q2','Q3','FY')",
        (company.company_id, fiscal_year),
    ).fetchall()
    periods = {p[0]: (p[1], p[2]) for p in prows}
    if not {"Q1", "Q2", "Q3", "FY"} <= periods.keys():
        return Abstention(f"{metric_key}_q4", ticker, "no_calendar", "missing fiscal-calendar periods")
    fy_start, fy_end = periods["FY"]
    if not periods_contiguous(fy_start, fy_end, [periods["Q1"], periods["Q2"], periods["Q3"]]):
        return Abstention(f"{metric_key}_q4", ticker, "non_tiling_periods",
                          "Q1-Q3 do not cleanly tile the fiscal year — refusing to subtract")
    value = _q4_derive(fy.value, q1.value, q2.value, q3.value)
    return Q4Result(
        ticker, metric_key, fiscal_year, value, mapping.unit, "derived", False, True,
        fy.citation,  # derived row's knowledge_time/citation = the FY fact (the 10-K)
        f"{fy.value} - {q1.value} - {q2.value} - {q3.value} = {value}", fy.caveat,
    )


# ---------- segment values (U10 — axis/member dimensional facts) ----------


@dataclass(frozen=True)
class SegmentResult:
    ticker: str
    metric_key: str
    member: str
    value: Decimal
    unit: str
    period_end: date
    citation: Citation
    caveat: str | None = None


def segment_value(
    conn: psycopg.Connection, ticker: str, metric_key: str, member: str, period: str, *,
    as_of: date | datetime, axis: str | None = None,
) -> SegmentResult | Abstention:
    """A single segment's value (e.g. NVIDIA 'Data Center' revenue). Same registry/as-of
    machinery as metric_value, but restricted to dimensional rows (axis IS NOT NULL) whose
    member matches. Abstains cleanly when no segment fact is present — including the current
    state where segment facts have not yet been ingested (see STATUS: segment-XBRL gap)."""
    as_of_dt = _to_dt(as_of)
    as_of_date = as_of_dt.date()
    company = resolve_one(conn, ticker)
    mapping = resolve_mapping(conn, metric_key, company.company_id, as_of_date)
    if mapping is None:
        return Abstention(f"{metric_key}_segment", ticker, "unmapped_metric", f"no mapping for {metric_key!r}")
    if mapping.us_gaap_tag is None:
        return Abstention(f"{metric_key}_segment", ticker, "no_comparable_mapping",
                          mapping.provenance or f"{metric_key} does not apply to {ticker}")
    fr = resolve_period(conn, company.company_id, ticker, period)
    facts = AsOfContext(conn, as_of_dt).facts(
        company_id=company.company_id, concept=mapping.us_gaap_tag, period_end=fr.period_end
    )
    rows = [
        f for f in facts
        if f["axis"] is not None and f["unit"] == mapping.unit
        and (f["member"] or "").lower() == member.lower()
        and (axis is None or f["axis"] == axis)
    ]
    if not rows:
        return Abstention(
            f"{metric_key}_segment", ticker, "no_segment_data",
            f"no {member!r} segment {metric_key} for {ticker} {_period_label(fr)} as of {as_of_date}",
        )
    row = max(rows, key=lambda f: f["knowledge_time"])
    return SegmentResult(
        ticker, metric_key, member, row["value"], mapping.unit, fr.period_end,
        Citation(row["accession"], _period_label(fr), as_of_date),
        None if mapping.comparable else mapping.provenance,
    )


def quarter_value(
    conn: psycopg.Connection, ticker: str, metric_key: str, fiscal_year: int, quarter: str, *,
    as_of: date | datetime,
):
    """One quarter's value: Q1-Q3 direct, Q4 via q4_value (derivation/preliminary)."""
    if quarter == "Q4":
        return q4_value(conn, ticker, metric_key, fiscal_year, as_of=as_of)
    return metric_value(conn, ticker, metric_key, f"{quarter} FY{fiscal_year}", as_of=as_of)


def derived_ttm(
    conn: psycopg.Connection, ticker: str, metric_key: str, *, as_of: date | datetime,
) -> DerivedResult | Abstention:
    """Trailing twelve months of an ADDITIVE metric: sum of the last four quarters known
    as-of (Q4 derived where needed). Non-additive metrics (EPS) abstain — summing quarterly
    EPS is invalid (share-count averaging)."""
    if metric_key not in ADDITIVE:
        return Abstention(f"{metric_key}_ttm", ticker, "non_additive",
                          f"TTM by summation is invalid for {metric_key} (e.g. EPS)")
    company = resolve_one(conn, ticker)
    as_of_date = _to_dt(as_of).date()
    rows = conn.execute(
        "SELECT fiscal_year, fiscal_period FROM fiscal_calendars"
        " WHERE company_id = %s AND fiscal_period IN ('Q1','Q2','Q3','Q4') AND period_end <= %s"
        " ORDER BY period_end DESC LIMIT 4",
        (company.company_id, as_of_date),
    ).fetchall()
    if len(rows) < 4:
        return Abstention(f"{metric_key}_ttm", ticker, "insufficient_quarters",
                          f"only {len(rows)} quarters known as of {as_of_date}")
    parts = [quarter_value(conn, ticker, metric_key, fy, fp, as_of=as_of) for fy, fp in rows]
    values, inputs = [], []
    for p in parts:
        if isinstance(p, Abstention):
            return Abstention(f"{metric_key}_ttm", ticker, "insufficient_data",
                              f"{p.reason}: {p.detail}")
        values.append(p.value)
        inputs.append(p)
    total = sum(values, Decimal(0))
    label = " + ".join(f"{fp} FY{fy}" for fy, fp in rows)
    return DerivedResult(
        "TTM", ticker, f"{metric_key} TTM (as of {as_of_date})", total, inputs[0].unit,
        f"{' + '.join(str(v) for v in values)} = {total}  [{label}]", inputs,
        _combine_caveats(*[i for i in inputs if isinstance(i, MetricResult)]),
    )
