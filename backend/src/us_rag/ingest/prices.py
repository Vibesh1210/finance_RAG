"""Market data (plan 2d, pins U6/§3.5): Tiingo EOD backfill + corporate actions,
Stooq cross-check.

Storage principle (§3.5): UNADJUSTED prices + an actions table, adjusted at query
time. Storing only adjusted series would back-propagate today's knowledge into
history — the point-in-time sin this project exists to avoid.

Raw Tiingo responses are cached to blobs/tiingo/ (parse_float=Decimal on read, so
values stay exact). The reconciliation check re-derives adjusted returns from our
unadjusted rows + actions and compares them with Tiingo's own adjusted series —
proving OUR adjustment math before anything downstream trusts it (gate check 5).

Live runs require TIINGO_API_KEY in .env ([HUMAN]: free registration, tiingo.com).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from datetime import date, timedelta
from decimal import Decimal

import httpx
import psycopg

from us_rag.db import connect
from us_rag.env import load_env, repo_root

TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"
STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&d1={d1}&d2={d2}&i=d"
CACHE_DIR = repo_root() / "blobs" / "tiingo"
PRICE_LEAD_DAYS = 14  # a little runway before FY2024 start, for return math

# reconciliation tolerances: split-adjusted daily returns must match Tiingo's
# adjusted returns except on dividend ex-dates (Tiingo adjusts for those too)
RETURN_TOLERANCE = Decimal("0.005")


class PricesError(RuntimeError):
    pass


def _tiingo_token() -> str:
    load_env()
    token = os.environ.get("TIINGO_API_KEY", "")
    if not token:
        raise PricesError(
            "TIINGO_API_KEY is empty — [HUMAN] task: register (free) at tiingo.com "
            "and put the key in .env, then rerun: python -m us_rag.ingest.prices"
        )
    return token


def price_window(conn: psycopg.Connection, company_id: int) -> tuple[date, date]:
    """[FY2024 start − lead, corpus close] from the company's own calendar/registry."""
    row = conn.execute(
        "SELECT period_start FROM fiscal_calendars WHERE company_id = %s"
        " AND fiscal_year = 2024 AND fiscal_period = 'FY'",
        (company_id,),
    ).fetchone()
    close = conn.execute(
        "SELECT max(acceptance_datetime)::date FROM documents"
        " WHERE company_id = %s AND corpus",
        (company_id,),
    ).fetchone()
    if not row or not close or close[0] is None:
        raise PricesError("fiscal calendar or corpus registry incomplete — load facts first")
    return row[0] - timedelta(days=PRICE_LEAD_DAYS), close[0]


def fetch_tiingo(ticker: str, start: date, end: date, *, refresh: bool = False) -> list[dict]:
    cache = CACHE_DIR / f"{ticker}.json"
    if not cache.exists() or refresh:
        response = httpx.get(
            TIINGO_URL.format(ticker=ticker.lower()),
            params={
                "startDate": str(start),
                "endDate": str(end),
                "token": _tiingo_token(),
                "format": "json",
            },
            timeout=60.0,
        )
        response.raise_for_status()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(response.text)
    return json.loads(cache.read_text(), parse_float=Decimal)


def load_prices(conn: psycopg.Connection, company_id: int, rows: list[dict]) -> dict:
    """Insert unadjusted OHLCV + actions. Idempotent (natural keys)."""
    inserted = splits = dividends = 0
    for row in rows:
        trade_date = date.fromisoformat(row["date"][:10])
        result = conn.execute(
            "INSERT INTO prices (company_id, trade_date, open, high, low, close,"
            " volume, source) VALUES (%s, %s, %s, %s, %s, %s, %s, 'tiingo')"
            " ON CONFLICT (company_id, trade_date) DO NOTHING",
            (
                company_id,
                trade_date,
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row["close"],
                row.get("volume"),
            ),
        )
        inserted += result.rowcount
        split_factor = row.get("splitFactor", 1)
        if split_factor and Decimal(str(split_factor)) != 1:
            conn.execute(
                "INSERT INTO corporate_actions (company_id, action_type, ex_date,"
                " factor, source) VALUES (%s, 'split', %s, %s, 'tiingo')"
                " ON CONFLICT (company_id, action_type, ex_date) DO NOTHING",
                (company_id, trade_date, Decimal(str(split_factor))),
            )
            splits += 1
        dividend = row.get("divCash", 0)
        if dividend and Decimal(str(dividend)) > 0:
            conn.execute(
                "INSERT INTO corporate_actions (company_id, action_type, ex_date,"
                " amount, source) VALUES (%s, 'dividend', %s, %s, 'tiingo')"
                " ON CONFLICT (company_id, action_type, ex_date) DO NOTHING",
                (company_id, trade_date, Decimal(str(dividend))),
            )
            dividends += 1
    return {"prices": inserted, "splits": splits, "dividends": dividends}


# ---------- checks (used by the gate) ----------


def split_adjusted_series(conn: psycopg.Connection, company_id: int) -> list[tuple[date, Decimal]]:
    """close × (product of split factors with ex_date AFTER the trade date) —
    query-time adjustment (U6), never stored."""
    factors = conn.execute(
        "SELECT ex_date, factor FROM corporate_actions"
        " WHERE company_id = %s AND action_type = 'split' ORDER BY ex_date",
        (company_id,),
    ).fetchall()
    out = []
    for trade_date, close in conn.execute(
        "SELECT trade_date, close FROM prices WHERE company_id = %s ORDER BY trade_date",
        (company_id,),
    ):
        adjustment = Decimal(1)
        for ex_date, factor in factors:
            if trade_date < ex_date:
                adjustment *= factor
        out.append((trade_date, close / adjustment))
    return out


def max_gap_days(conn: psycopg.Connection, company_id: int) -> int:
    dates = [
        row[0]
        for row in conn.execute(
            "SELECT trade_date FROM prices WHERE company_id = %s ORDER BY trade_date",
            (company_id,),
        )
    ]
    if len(dates) < 2:
        return 999
    return max((b - a).days for a, b in zip(dates, dates[1:]))


def reconcile_with_tiingo_adjusted(
    conn: psycopg.Connection, company_id: int, tiingo_rows: list[dict]
) -> list[str]:
    """Split-adjusted daily returns from OUR store vs Tiingo's adjClose returns.
    Mismatches are allowed only on dividend ex-dates (their adjClose folds
    dividends in; our pinned answer basis is split-adjusted only, U6)."""
    ours = dict(split_adjusted_series(conn, company_id))
    theirs = {
        date.fromisoformat(r["date"][:10]): Decimal(str(r["adjClose"])) for r in tiingo_rows
    }
    div_dates = {
        row[0]
        for row in conn.execute(
            "SELECT ex_date FROM corporate_actions"
            " WHERE company_id = %s AND action_type = 'dividend'",
            (company_id,),
        )
    }
    shared = sorted(set(ours) & set(theirs))
    problems = []
    for previous, current in zip(shared, shared[1:]):
        if current in div_dates:
            continue
        our_return = ours[current] / ours[previous]
        their_return = theirs[current] / theirs[previous]
        if abs(our_return - their_return) > RETURN_TOLERANCE:
            problems.append(
                f"{current}: split-adjusted return {our_return:.6f} vs Tiingo {their_return:.6f}"
            )
    return problems


def stooq_closes(ticker: str, start: date, end: date) -> dict[date, Decimal]:
    """Keyless Stooq CSV (adjusted-only — documented fallback limitation, §3.5)."""
    url = STOOQ_URL.format(
        symbol=ticker.lower(), d1=start.strftime("%Y%m%d"), d2=end.strftime("%Y%m%d")
    )
    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    out = {}
    for row in csv.DictReader(io.StringIO(response.text)):
        try:
            out[date.fromisoformat(row["Date"])] = Decimal(row["Close"])
        except (KeyError, ValueError):
            continue
    return out


def cross_check_stooq(conn: psycopg.Connection, company_id: int, ticker: str) -> list[str]:
    """Independent-vendor sanity: our split-adjusted closes vs Stooq's, last 30
    shared sessions, 2% tolerance (different vendors, different rounding)."""
    ours = dict(split_adjusted_series(conn, company_id))
    if not ours:
        return ["no local prices to check"]
    last = sorted(ours)[-1]
    theirs = stooq_closes(ticker, last - timedelta(days=60), last)
    shared = sorted(set(ours) & set(theirs))[-30:]
    if len(shared) < 10:
        return [f"only {len(shared)} shared sessions with Stooq"]
    problems = []
    for day in shared:
        ratio = ours[day] / theirs[day]
        if not (Decimal("0.98") <= ratio <= Decimal("1.02")):
            problems.append(f"{day}: ours {ours[day]} vs stooq {theirs[day]}")
    return problems


def backfill_prices(tickers: list[str] | None = None, *, refresh: bool = False) -> list[dict]:
    universe = json.loads((repo_root() / "universe.json").read_text())
    if tickers:
        universe = [e for e in universe if e["ticker"] in tickers]
    summaries = []
    with connect() as conn:
        for entry in universe:
            ticker = entry["ticker"]
            company_id = conn.execute(
                "SELECT company_id FROM companies WHERE cik = %s", (entry["cik"],)
            ).fetchone()[0]
            start, end = price_window(conn, company_id)
            rows = fetch_tiingo(ticker, start, end, refresh=refresh)
            summary = {"ticker": ticker, "window": [str(start), str(end)],
                       **load_prices(conn, company_id, rows)}
            conn.commit()
            summaries.append(summary)
            print(json.dumps(summary))
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tiingo EOD backfill + actions")
    parser.add_argument("--tickers", nargs="*")
    parser.add_argument("--refresh", action="store_true")
    backfill_prices(parser.parse_args().tickers, refresh=parser.parse_args().refresh)
