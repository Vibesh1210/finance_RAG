"""Pinned universe (U1) and deterministic universe.json derivation.

universe.json is DERIVED from fixtures/company_tickers.json plus the constants
below. Never hand-edit it: the Phase 0 gate re-derives it byte-for-byte
(ADR-0003). The design table's CIK column is a hint only; the SEC
snapshot wins on any mismatch (surfaced as a warning, recorded in an ADR (docs/production/adr/)).
"""

from __future__ import annotations

import json
from pathlib import Path

# (ticker, sector, fye_month_hint, 52/53-week calendar, design-table CIK hint)
# fye_month_hint is a HINT for humans; real fiscal boundaries come from
# fiscal_calendars, populated from filing contexts (pin U8, design §4.6).
PINNED_UNIVERSE = [
    ("AAPL", "tech hardware", 9, True, "0000320193"),
    ("CAT", "industrials", 12, False, "0000018230"),
    ("COST", "retail", 9, True, "0000909832"),
    ("DE", "industrials", 10, True, "0000315189"),
    ("JNJ", "healthcare", 12, True, "0000200406"),
    ("JPM", "banking", 12, False, "0000019617"),
    ("MSFT", "software/cloud", 6, False, "0000789019"),
    ("NVDA", "semiconductors", 1, True, "0001045810"),
    ("WMT", "retail", 1, False, "0000104169"),
    ("XOM", "energy", 12, False, "0000034088"),
]

# Ticker→CIK is itself point-in-time (design §4.3). When a successor registrant takes
# a ticker, the live snapshot maps to the entity that holds the listing *today*, not
# the one that filed the corpus-window documents. Overrides pin the filing entity;
# each carries the reason and lands in an ADR (docs/production/adr/).
CIK_OVERRIDES = {
    # ADR-0004: ExxonMobil holding-company reorganization, effective 2026-07-01
    # (8-K12B by successor CIK 0002115436, "ExxonMobil Holdings Corp"). All FY2024/
    # FY2025 filings live under the predecessor below; the successor has no 10-K/10-Q.
    "XOM": (
        "0000034088",
        "Exxon Mobil Corp (predecessor registrant)",
        "successor ExxonMobil Holdings Corp (CIK 0002115436) took the XOM ticker "
        "2026-07-01 via 8-K12B; corpus-window filings live under this CIK",
    ),
}


def build_universe(snapshot_path: Path) -> str:
    """Return canonical universe.json text derived from the committed SEC snapshot."""
    snapshot = json.loads(snapshot_path.read_text())
    by_ticker = {row["ticker"].upper(): row for row in snapshot.values()}
    entries = []
    for ticker, sector, fye_hint, wk5253, design_cik in PINNED_UNIVERSE:
        row = by_ticker.get(ticker)
        if row is None:
            raise LookupError(f"ticker {ticker} not found in snapshot {snapshot_path}")
        entry = {
            "ticker": ticker,
            "cik": f"{int(row['cik_str']):010d}",
            "name": row["title"],
            "sector": sector,
            "fye_month_hint": fye_hint,
            "week_52_53_calendar": wk5253,
        }
        if ticker in CIK_OVERRIDES:
            cik, name, note = CIK_OVERRIDES[ticker]
            entry.update({"cik": cik, "name": name, "cik_note": note})
        if entry["cik"] != design_cik:
            print(
                f"WARNING {ticker}: design-table CIK {design_cik} != resolved "
                f"{entry['cik']} — snapshot wins; add an ADR note."
            )
        entries.append(entry)
    return json.dumps(entries, indent=2) + "\n"
