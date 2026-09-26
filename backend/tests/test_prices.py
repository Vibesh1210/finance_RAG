"""Prices module tests (plan 2d), fixtures-only — synthetic Tiingo rows exercise
the NVDA-split shape: unadjusted storage, actions extraction, query-time
adjustment, and the adjusted-returns reconciliation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from us_rag.ingest.prices import (
    load_prices,
    max_gap_days,
    reconcile_with_tiingo_adjusted,
    split_adjusted_series,
)

# a 10:1 split on day 3 (like NVDA 2024-06-10), then a dividend on day 5
SYNTHETIC = [
    {"date": "2024-06-06T00:00:00.000Z", "close": Decimal("1200"), "open": Decimal("1190"),
     "high": Decimal("1210"), "low": Decimal("1180"), "volume": 100,
     "adjClose": Decimal("120"), "splitFactor": 1, "divCash": 0},
    {"date": "2024-06-07T00:00:00.000Z", "close": Decimal("1210"), "open": Decimal("1200"),
     "high": Decimal("1215"), "low": Decimal("1195"), "volume": 100,
     "adjClose": Decimal("121"), "splitFactor": 1, "divCash": 0},
    {"date": "2024-06-10T00:00:00.000Z", "close": Decimal("122"), "open": Decimal("121"),
     "high": Decimal("123"), "low": Decimal("120"), "volume": 1000,
     "adjClose": Decimal("122"), "splitFactor": Decimal("10.0"), "divCash": 0},
    {"date": "2024-06-11T00:00:00.000Z", "close": Decimal("125"), "open": Decimal("122"),
     "high": Decimal("126"), "low": Decimal("121"), "volume": 1000,
     "adjClose": Decimal("125"), "splitFactor": 1, "divCash": 0},
    {"date": "2024-06-12T00:00:00.000Z", "close": Decimal("124"), "open": Decimal("125"),
     "high": Decimal("125"), "low": Decimal("123"), "volume": 1000,
     "adjClose": Decimal("124"), "splitFactor": 1, "divCash": Decimal("0.01")},
]


def test_load_prices_stores_unadjusted_and_extracts_actions(conn, company_id):
    nvda = company_id("NVDA")
    summary = load_prices(conn, nvda, SYNTHETIC)
    assert summary == {"prices": 5, "splits": 1, "dividends": 1}
    # unadjusted: the pre-split close is stored at its printed 1200, not 120
    stored = conn.execute(
        "SELECT close FROM prices WHERE company_id = %s AND trade_date = '2024-06-06'",
        (nvda,),
    ).fetchone()[0]
    assert stored == Decimal("1200")
    action = conn.execute(
        "SELECT factor FROM corporate_actions WHERE company_id = %s"
        " AND action_type = 'split'",
        (nvda,),
    ).fetchone()
    assert action[0] == Decimal("10.0")
    # idempotent
    assert load_prices(conn, nvda, SYNTHETIC)["prices"] == 0


def test_split_adjustment_at_query_time(conn, company_id):
    nvda = company_id("NVDA")
    load_prices(conn, nvda, SYNTHETIC)
    series = dict(split_adjusted_series(conn, nvda))
    assert series[date(2024, 6, 6)] == Decimal("120")  # 1200 / 10
    assert series[date(2024, 6, 11)] == Decimal("125")  # post-split: untouched


def test_reconciliation_against_vendor_adjusted(conn, company_id):
    nvda = company_id("NVDA")
    load_prices(conn, nvda, SYNTHETIC)
    assert reconcile_with_tiingo_adjusted(conn, nvda, SYNTHETIC) == []
    # corrupt one adjClose → the reconciliation must catch it
    broken = [dict(r) for r in SYNTHETIC]
    broken[1]["adjClose"] = Decimal("140")
    problems = reconcile_with_tiingo_adjusted(conn, nvda, broken)
    assert problems, "corrupted vendor series must not reconcile"


def test_gap_detector(conn, company_id):
    nvda = company_id("NVDA")
    load_prices(conn, nvda, SYNTHETIC[:2] + SYNTHETIC[3:])  # drop the split day row
    assert max_gap_days(conn, nvda) == 4  # 06-07 → 06-11
