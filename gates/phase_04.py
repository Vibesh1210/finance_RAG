"""Phase 4 gate: SQL branch — metric registry, executor, Q4 derivation, verifier
(execution plan Phase 4).

Deterministic path: execution_v0 must match exactly (no tolerance). Segment SQL is
deferred (DECISIONS #13) — segment questions ride the Phase 3 narrative path for M0, so
this gate checks only that the segment executor fails safe, not SQL exact-match.

Loads bge-m3? No — the SQL path is model-free. It seeds the registry + applies migrations
(idempotent) so the gate is self-sufficient, then runs everything read-only.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import yaml

from common import ROOT, run_gate

from us_rag.db import connect, connect_ro
from us_rag.query.metrics import (
    Abstention,
    CompareResult,
    SeriesResult,
    derived_margin,
    derived_ttm,
    derived_yoy,
    metric_compare,
    metric_series,
    metric_value,
    q4_value,
    seed_metric_mappings,
    segment_value,
)
from us_rag.query.verify import verify
from us_rag.store.migrate import migrate

EXECUTION = ROOT / "golden" / "execution_v0.yaml"
NOW = date(2026, 3, 1)


def _setup() -> None:
    migrate()  # ensure 003 (nullable tag, unique indexes, read-only role) is applied
    with connect() as conn:
        seed_metric_mappings(conn)


def _run(conn, e: dict):
    t = e["template"]
    if t == "metric_value":
        return metric_value(conn, e["ticker"], e["metric"], e["period"], as_of=e["as_of"])
    if t == "q4":
        return q4_value(conn, e["ticker"], e["metric"], e["fiscal_year"], as_of=e["as_of"])
    if t == "derived_margin":
        return derived_margin(conn, e["ticker"], e["period"], as_of=e["as_of"], name=e.get("name", "gross_margin"))
    if t == "metric_compare":
        return metric_compare(conn, e["tickers"], e["metric"], e["period"], as_of=e["as_of"])
    if t == "metric_series":
        return metric_series(conn, e["ticker"], e["metric"], last_n=e["last_n"], as_of=e["as_of"])
    if t == "ttm":
        return derived_ttm(conn, e["ticker"], e["metric"], as_of=e["as_of"])
    raise AssertionError(f"{e['id']}: unknown template {t!r}")


def _check_entry(r, exp: dict) -> str | None:
    """Return a mismatch string, or None if the result matches the expectation exactly.
    Dispatch on the RESULT type (not on which keys `expect` carries — a metric_value can
    also assert a `comparable` flag)."""
    if "abstain" in exp:
        if not isinstance(r, Abstention):
            return "expected abstain, got a value"
        want = exp["abstain"]
        return None if want in (None, r.reason) else f"abstain reason {r.reason} != {want}"
    if isinstance(r, CompareResult):
        if "comparable" in exp and r.comparable != exp["comparable"]:
            return f"comparable {r.comparable} != {exp['comparable']}"
        if "values" in exp and [str(x.value) for x in r.results] != [str(v) for v in exp["values"]]:
            return "compare leg values differ"
        return None
    if isinstance(r, SeriesResult):
        got = [str(p.value) for p in r.points]
        return None if got == [str(v) for v in exp["values"]] else f"series {got} != {exp['values']}"
    # single value expectation
    if isinstance(r, Abstention):
        return f"expected a value, got abstain ({r.reason})"
    if Decimal(str(r.value)) != Decimal(str(exp["value"])):
        return f"value {r.value} != {exp['value']}"
    if "accession" in exp and getattr(r, "citation", None) and r.citation.accession != exp["accession"]:
        return f"citation {r.citation.accession} != {exp['accession']}"
    if exp.get("comparable") is False and getattr(r, "comparable", True) is not False:
        return "expected non-comparable"
    if exp.get("derived") and not getattr(r, "derived", False):
        return "expected a derived result"
    return None


def check_execution_v0_exact_match() -> None:
    entries = yaml.safe_load(EXECUTION.read_text())
    misses = []
    with connect_ro() as ro:
        for e in entries:
            mismatch = _check_entry(_run(ro, e), e["expect"])
            if mismatch:
                misses.append(f"{e['id']}: {mismatch}")
    if misses:
        raise AssertionError(f"{len(misses)}/{len(entries)} execution_v0 mismatches: " + "; ".join(misses))


def check_registry() -> None:
    with connect_ro() as ro:
        defaults = ro.execute("SELECT count(*) FROM metric_mappings WHERE company_id IS NULL").fetchone()[0]
        abstains = ro.execute("SELECT count(*) FROM metric_mappings WHERE us_gaap_tag IS NULL").fetchone()[0]
    if defaults < 12:
        raise AssertionError(f"registry has {defaults} default metrics, expected >= 12")
    if abstains < 2:
        raise AssertionError(f"registry has {abstains} abstention rows, expected >= 2 (JPM gross profit / cost of revenue)")


def check_q4_derivation() -> None:
    """NVDA Q4 FY2025 revenue must equal FY - (Q1+Q2+Q3) exactly, and be a derived row."""
    with connect_ro() as ro:
        fy = metric_value(ro, "NVDA", "revenue", "FY2025", as_of=NOW).value
        qs = [metric_value(ro, "NVDA", "revenue", f"{q} FY2025", as_of=NOW).value for q in ("Q1", "Q2", "Q3")]
        q4 = q4_value(ro, "NVDA", "revenue", 2025, as_of=NOW)
    if isinstance(q4, Abstention):
        raise AssertionError(f"NVDA Q4 abstained: {q4.detail}")
    if q4.value != fy - sum(qs):
        raise AssertionError(f"Q4 {q4.value} != FY - sumQ1-3 {fy - sum(qs)}")
    if not q4.derived:
        raise AssertionError("NVDA Q4 revenue should be a derived row")


def check_jpm_behaviors() -> None:
    with connect_ro() as ro:
        rev = metric_value(ro, "JPM", "revenue", "FY2025", as_of=NOW)
        gp = metric_value(ro, "JPM", "gross_profit", "FY2025", as_of=NOW)
        gm = derived_margin(ro, "JPM", "FY2025", as_of=NOW)
    if getattr(rev, "comparable", True) is not False or not rev.caveat:
        raise AssertionError("JPM revenue must resolve comparable=false with a caveat")
    if not isinstance(gp, Abstention) or not isinstance(gm, Abstention):
        raise AssertionError("JPM gross profit and gross margin must abstain")


def check_no_llm_arithmetic() -> None:
    """Every derived number carries a computation record, and the verifier rejects one
    that doesn't — the structural guarantee behind the no-LLM-arithmetic rule."""
    from us_rag.query.metrics import DerivedResult

    with connect_ro() as ro:
        yoy = derived_yoy(ro, "NVDA", "revenue", 2025, as_of=NOW)
    if not getattr(yoy, "computation", None):
        raise AssertionError("derived YoY is missing its computation record")
    stripped = DerivedResult("YoY", "NVDA", "x", yoy.value, "ratio", "", [], None)
    if verify(stripped, claimed_value=str(yoy.value)).ok:
        raise AssertionError("verifier accepted a derived number with no computation record")


def check_segment_deferred_fails_safe() -> None:
    """DECISIONS #13: segment-SQL deferred; the executor must abstain cleanly, not error."""
    with connect_ro() as ro:
        r = segment_value(ro, "NVDA", "revenue", "Data Center", "FY2025", as_of=NOW)
    if not isinstance(r, Abstention) or r.reason != "no_segment_data":
        raise AssertionError(f"segment executor should abstain no_segment_data, got {r}")


_setup()
run_gate(
    "phase_04",
    [
        ("registry seeded: >=12 default metrics, JPM abstention rows present", check_registry),
        ("execution_v0 exact-match 100% (deterministic, no tolerance)", check_execution_v0_exact_match),
        ("Q4 derivation: NVDA Q4 FY2025 revenue = FY - sum(Q1..Q3), derived row", check_q4_derivation),
        ("JPM behaviors: revenue caveated non-comparable; gross profit/margin abstain", check_jpm_behaviors),
        ("no-LLM-arithmetic: derived numbers carry a computation record; verifier enforces", check_no_llm_arithmetic),
        ("segment-SQL deferred (DECISIONS #13): executor abstains no_segment_data", check_segment_deferred_fails_safe),
    ],
)
