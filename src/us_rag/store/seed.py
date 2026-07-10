"""Idempotent seeds: security master from universe.json; fiscal calendars from
fixtures/fiscal_seeds.json (hand-entered from filings, [HUMAN]-verified; Phase 2
re-derives every row from XBRL contexts — a mismatch there is a gate failure)."""

from __future__ import annotations

import json
from datetime import date

from us_rag.db import connect
from us_rag.env import repo_root

# Ticker validity: '1970-01-01' means "since before anything we model" (design §4.3).
TICKER_EPOCH = date(1970, 1, 1)

# Curated aliases for entity resolution (design §6.6). Ambiguity is representable —
# the table allows the same alias on two companies; resolution must surface it.
ALIASES = {
    "AAPL": ["Apple"],
    "MSFT": ["Microsoft"],
    "NVDA": ["NVIDIA", "Nvidia"],
    "WMT": ["Walmart", "Wal-Mart"],
    "COST": ["Costco"],
    "JPM": ["JPMorgan", "JP Morgan", "JPMorgan Chase"],
    "XOM": ["Exxon", "ExxonMobil", "Exxon Mobil"],
    "JNJ": ["Johnson & Johnson", "J&J"],
    "CAT": ["Caterpillar"],
    "DE": ["Deere", "John Deere"],
}


def seed_security_master(url: str | None = None) -> None:
    universe = json.loads((repo_root() / "universe.json").read_text())
    with connect(url) as conn:
        for entry in universe:
            row = conn.execute(
                """
                INSERT INTO companies (cik, name, sector, fye_month_hint, week_52_53_calendar)
                VALUES (%(cik)s, %(name)s, %(sector)s, %(fye_month_hint)s, %(week_52_53_calendar)s)
                ON CONFLICT (cik) DO UPDATE
                    SET name = EXCLUDED.name, sector = EXCLUDED.sector,
                        fye_month_hint = EXCLUDED.fye_month_hint,
                        week_52_53_calendar = EXCLUDED.week_52_53_calendar
                RETURNING company_id
                """,
                entry,
            ).fetchone()
            company_id = row[0]
            conn.execute(
                """
                INSERT INTO tickers (company_id, ticker, valid_from, note)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (company_id, ticker, valid_from) DO UPDATE SET note = EXCLUDED.note
                """,
                (company_id, entry["ticker"], TICKER_EPOCH, entry.get("cik_note")),
            )
            for alias in [entry["name"], *ALIASES.get(entry["ticker"], [])]:
                conn.execute(
                    "INSERT INTO name_aliases (company_id, alias) VALUES (%s, %s)"
                    " ON CONFLICT DO NOTHING",
                    (company_id, alias),
                )
        conn.commit()


def seed_fiscal_calendars(url: str | None = None) -> None:
    seeds = json.loads((repo_root() / "fixtures" / "fiscal_seeds.json").read_text())
    with connect(url) as conn:
        for row in seeds["rows"]:
            company = conn.execute(
                "SELECT company_id FROM companies c JOIN tickers t USING (company_id)"
                " WHERE t.ticker = %s",
                (row["ticker"],),
            ).fetchone()
            if company is None:
                raise LookupError(f"seed references unknown ticker {row['ticker']}")
            conn.execute(
                """
                INSERT INTO fiscal_calendars
                    (company_id, fiscal_year, fiscal_period, period_start, period_end,
                     weeks, source)
                VALUES (%s, %s, %s, %s, %s, %s, 'seed')
                ON CONFLICT (company_id, fiscal_year, fiscal_period) DO UPDATE
                    SET period_start = EXCLUDED.period_start,
                        period_end = EXCLUDED.period_end,
                        weeks = EXCLUDED.weeks
                    WHERE fiscal_calendars.source = 'seed'  -- xbrl rows are never clobbered by seeds
                """,
                (
                    company[0],
                    row["fiscal_year"],
                    row["fiscal_period"],
                    row["period_start"],
                    row["period_end"],
                    row.get("weeks"),
                ),
            )
        conn.commit()


if __name__ == "__main__":
    seed_security_master()
    seed_fiscal_calendars()
    print("seeded: security master + fiscal calendars")
