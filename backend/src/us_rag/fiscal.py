"""Fiscal resolver (design §4.6, pin U8): periods are RESOLVED from fiscal_calendars,
never computed. There is no formula fallback anywhere in this module — a period
absent from the table is an error (FiscalGapError). The Phase 1 lint bans timedelta
construction and month arithmetic here; date *subtraction* (for overlap comparison
of stored rows) is the only arithmetic present.

Ambiguity policy (design §4.6):
- "Q3 FY2025"  → explicit, unambiguous.
- "Q3 2024"    → the company's fiscal Q3 of FY2024; ambiguous=True unless the
                 company's fiscal year IS the calendar year (then it's just Q3).
- bare "2024"  → year-level policy: the fiscal year with majority overlap of
                 calendar 2024; always ambiguous unless fiscal == calendar; the
                 interpretation string states the mapping explicitly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg.rows import dict_row


class FiscalGapError(LookupError):
    """U8: the requested period is not in fiscal_calendars — never fall back to a formula."""


@dataclass(frozen=True)
class FiscalResolution:
    company_id: int
    ticker: str
    fiscal_year: int
    fiscal_period: str  # 'FY' | 'Q1'..'Q4'
    period_start: date
    period_end: date
    interpretation: str  # human-readable mapping; answers must surface it when ambiguous
    ambiguous: bool
    fiscal_equals_calendar: bool


_QN_FY = re.compile(r"\bQ([1-4])\s*FY\s*(\d{4})\b", re.IGNORECASE)
_FY = re.compile(r"\bFY\s*(\d{4})\b", re.IGNORECASE)
_QN_YEAR = re.compile(r"\bQ([1-4])\s+(\d{4})\b", re.IGNORECASE)
_BARE_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _lookup(conn: psycopg.Connection, company_id: int, fy: int, period: str) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "SELECT * FROM fiscal_calendars WHERE company_id = %s AND fiscal_year = %s"
            " AND fiscal_period = %s",
            (company_id, fy, period),
        ).fetchone()
    if row is None:
        raise FiscalGapError(
            f"no fiscal_calendars row for company {company_id} FY{fy} {period} — "
            "U8 forbids computing it; ingest or seed the period"
        )
    return row


def _fy_equals_calendar(conn: psycopg.Connection, company_id: int, year: int) -> bool:
    """Data-driven check: is this company's FY<year> exactly calendar <year>?"""
    try:
        row = _lookup(conn, company_id, year, "FY")
    except FiscalGapError:
        return False
    return row["period_start"] == date(year, 1, 1) and row["period_end"] == date(year, 12, 31)


def resolve(conn: psycopg.Connection, company_id: int, ticker: str, text: str) -> FiscalResolution:
    """Resolve the first fiscal-period expression found in `text` for one company."""

    if match := _QN_FY.search(text):
        quarter, fy = f"Q{match.group(1)}", int(match.group(2))
        row = _lookup(conn, company_id, fy, quarter)
        return FiscalResolution(
            company_id, ticker, fy, quarter, row["period_start"], row["period_end"],
            f"{ticker} {quarter} FY{fy} = {row['period_start']} → {row['period_end']}",
            ambiguous=False,
            fiscal_equals_calendar=_fy_equals_calendar(conn, company_id, fy),
        )

    if match := _FY.search(text):
        fy = int(match.group(1))
        row = _lookup(conn, company_id, fy, "FY")
        return FiscalResolution(
            company_id, ticker, fy, "FY", row["period_start"], row["period_end"],
            f"{ticker} FY{fy} = {row['period_start']} → {row['period_end']}",
            ambiguous=False,
            fiscal_equals_calendar=_fy_equals_calendar(conn, company_id, fy),
        )

    if match := _QN_YEAR.search(text):
        quarter, year = f"Q{match.group(1)}", int(match.group(2))
        row = _lookup(conn, company_id, year, quarter)
        same = _fy_equals_calendar(conn, company_id, year)
        note = (
            f"{ticker} {quarter} {year}: fiscal and calendar quarters coincide "
            f"({row['period_start']} → {row['period_end']})"
            if same
            else f"'{quarter} {year}' interpreted as {ticker} fiscal {quarter} FY{year} "
            f"({row['period_start']} → {row['period_end']}) — say so in the answer"
        )
        return FiscalResolution(
            company_id, ticker, year, quarter, row["period_start"], row["period_end"],
            note, ambiguous=not same, fiscal_equals_calendar=same,
        )

    if match := _BARE_YEAR.search(text):
        year = int(match.group(0))
        if _fy_equals_calendar(conn, company_id, year):
            row = _lookup(conn, company_id, year, "FY")
            return FiscalResolution(
                company_id, ticker, year, "FY", row["period_start"], row["period_end"],
                f"{ticker} FY{year} is the calendar year {year}",
                ambiguous=False, fiscal_equals_calendar=True,
            )
        # majority-overlap over STORED rows (comparison of dates, not construction)
        cal_start, cal_end = date(year, 1, 1), date(year, 12, 31)
        best, best_overlap = None, -1
        for fy in (year, year + 1):
            try:
                row = _lookup(conn, company_id, fy, "FY")
            except FiscalGapError:
                continue
            overlap = (
                min(row["period_end"], cal_end) - max(row["period_start"], cal_start)
            ).days
            if overlap > best_overlap:
                best, best_overlap, best_fy = row, overlap, fy
        if best is None or best_overlap <= 0:
            raise FiscalGapError(
                f"cannot map calendar {year} for {ticker}: no overlapping FY rows "
                "in fiscal_calendars (U8: no formula fallback)"
            )
        return FiscalResolution(
            company_id, ticker, best_fy, "FY", best["period_start"], best["period_end"],
            f"calendar {year} ≈ {ticker} FY{best_fy} "
            f"({best['period_start']} → {best['period_end']}) — say so in the answer",
            ambiguous=True, fiscal_equals_calendar=False,
        )

    raise FiscalGapError(f"no fiscal-period expression found in {text!r}")
