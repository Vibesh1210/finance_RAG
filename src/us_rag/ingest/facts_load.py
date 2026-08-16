"""Facts load (plan 2b): companyfacts → bitemporal facts + fiscal_calendars.

Hard rules implemented here:
- fy/fp NEVER touch period identity (design §3.2): a fact's period is its context
  start/end dates, full stop — gate-tested with a deliberately lying fy/fp.
- knowledge_time = the reporting accession's EDGAR acceptance datetime (§4.2).
- Decimal-exact: companyfacts is parsed with parse_float=Decimal so no value ever
  passes through a float (units.normalize_xbrl enforces).
- Load scope (DECISIONS.md #9): every (concept, unit, period) identity group that
  at least one CORPUS accession reports — all corpus entries, plus the LATEST
  pre-corpus entry as the as-reported-then baseline. Baseline accessions are
  registered as metadata-only documents (corpus = FALSE, no blob), so historical
  knowledge_time stays exact without widening the corpus.
- Supersession pass (U11): within each identity group in knowledge order, a newer
  DIFFERENT value supersedes every older still-authoritative row (write-once link,
  DB-trigger enforced; done via store.asof.supersede only).

Fiscal calendars are re-derived from reported contexts (source='xbrl') and must
agree with the Phase 1 seeds — a mismatch raises, never overwrites (pin U8).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

import psycopg

from us_rag.db import connect
from us_rag.ingest.backfill import annual_windows, companyfacts_path, load_cached_submissions
from us_rag.ingest.edgar import Filing
from us_rag.store.asof import insert_fact, supersede
from us_rag.units import normalize_xbrl

PERIODIC_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}
# Quarter lengths actually observed in this universe: month-based calendars run
# ~90 days; week-based run 13/14 weeks — except COST, which reports 12/12/12/16
# (17 in 53-week years). Contiguity from the reported FY start is the real
# identifier; this range only filters out YTD durations.
_QUARTER_DAYS = range(82, 121)
_QUARTER_WEEKS = {12, 13, 14, 16, 17}
_VALIDATED_UNITS = {"USD", "USD/shares", "shares", "pure"}
CORPUS_FISCAL_YEARS = (2024, 2025)


class FactsLoadError(RuntimeError):
    """Fail-closed: ambiguous or contradictory source data stops the load."""


@dataclass(frozen=True)
class XbrlEntry:
    concept: str  # 'Revenues' (us-gaap) or 'dei:...' for other taxonomies
    unit: str
    value: Decimal | int
    period_start: date | None
    period_end: date
    accession: str
    form: str


def load_companyfacts(cik: str) -> dict:
    return json.loads(companyfacts_path(cik).read_text(), parse_float=Decimal)


def iter_entries(companyfacts: dict) -> list[XbrlEntry]:
    """Flatten + dedupe. The same (accession, period) may appear twice (frame
    annotations); identical values collapse, contradictory ones are fatal."""
    seen: dict[tuple, XbrlEntry] = {}
    for taxonomy, concepts in companyfacts.get("facts", {}).items():
        for tag, concept in concepts.items():
            name = tag if taxonomy == "us-gaap" else f"{taxonomy}:{tag}"
            for unit, entries in concept.get("units", {}).items():
                for raw in entries:
                    if raw.get("form") not in PERIODIC_FORMS:
                        continue  # 8-K facts exist only via U13 (design §4.2)
                    if raw.get("val") is None:
                        continue
                    start = raw.get("start")
                    entry = XbrlEntry(
                        concept=name,
                        unit=unit,
                        value=raw["val"],
                        period_start=date.fromisoformat(start) if start else None,
                        period_end=date.fromisoformat(raw["end"]),
                        accession=raw["accn"],
                        form=raw["form"],
                        # NOTE: raw['fy']/raw['fp'] are deliberately not read —
                        # period identity is the context dates alone (§3.2)
                    )
                    key = (name, unit, entry.period_start, entry.period_end, entry.accession)
                    if key in seen and seen[key].value != entry.value:
                        raise FactsLoadError(f"contradictory duplicate in companyfacts: {key}")
                    seen[key] = entry
    return list(seen.values())


def _corpus_acceptance(conn: psycopg.Connection, company_id: int) -> dict[str, datetime]:
    return {
        accession: acceptance
        for accession, acceptance in conn.execute(
            "SELECT accession, acceptance_datetime FROM documents"
            " WHERE company_id = %s AND corpus",
            (company_id,),
        )
    }


def select_rows(
    entries: list[XbrlEntry],
    corpus_acceptance: dict[str, datetime],
    filings_by_accession: dict[str, Filing],
) -> tuple[list[tuple[XbrlEntry, datetime]], list[Filing], int]:
    """Apply the load-scope rule. Returns (rows_with_knowledge_time,
    baseline_filings_to_register, skipped_unresolvable)."""
    groups: dict[tuple, list[XbrlEntry]] = defaultdict(list)
    for entry in entries:
        groups[(entry.concept, entry.unit, entry.period_start, entry.period_end)].append(entry)

    rows: list[tuple[XbrlEntry, datetime]] = []
    baselines: dict[str, Filing] = {}
    skipped = 0
    for group in groups.values():
        corpus_entries = [e for e in group if e.accession in corpus_acceptance]
        if not corpus_entries:
            continue  # group never touched by the corpus — out of scope
        for entry in corpus_entries:
            rows.append((entry, corpus_acceptance[entry.accession]))
        earliest_corpus = min(corpus_acceptance[e.accession] for e in corpus_entries)
        pre = []
        for entry in group:
            if entry.accession in corpus_acceptance:
                continue
            filing = filings_by_accession.get(entry.accession)
            if filing is None:
                skipped += 1  # ancient accession beyond the cached submissions window
                continue
            if filing.acceptance < earliest_corpus:
                pre.append((filing.acceptance, entry, filing))
        if pre:
            acceptance, entry, filing = max(pre, key=lambda item: item[0])
            rows.append((entry, acceptance))
            baselines[filing.accession] = filing
    rows.sort(key=lambda item: item[1])  # knowledge order
    return rows, list(baselines.values()), skipped


def insert_rows(
    conn: psycopg.Connection, company_id: int, rows: list[tuple[XbrlEntry, datetime]]
) -> int:
    existing = {
        tuple(row)
        for row in conn.execute(
            "SELECT concept, unit, period_start, period_end, accession FROM facts"
            " WHERE company_id = %s AND source IN ('10-K', '10-Q')",
            (company_id,),
        )
    }
    inserted = 0
    for entry, knowledge_time in rows:
        key = (entry.concept, entry.unit, entry.period_start, entry.period_end, entry.accession)
        if key in existing:
            continue
        if entry.unit in _VALIDATED_UNITS:
            normalize_xbrl(entry.value, entry.unit)  # exactness guard, not a transform
        insert_fact(
            conn,
            company_id=company_id,
            concept=entry.concept,
            axis=None,
            member=None,
            value=entry.value,
            unit=entry.unit,
            period_start=entry.period_start,
            period_end=entry.period_end,
            period_kind="duration" if entry.period_start else "instant",
            knowledge_time=knowledge_time,
            accession=entry.accession,
            source=entry.form.split("/")[0],  # 10-K/A reports as a 10-K
            preliminary=False,
            human_verified=False,
        )
        inserted += 1
    return inserted


# ---------- fiscal calendars from contexts (pin U8) ----------


def derive_calendar(
    entries: list[XbrlEntry],
    fy_window: tuple[date, date],
    *,
    week_based: bool,
    corpus_acceptance: dict[str, datetime] | None = None,
) -> list[tuple[str, date, date, int | None, str]]:
    """(period, start, end, weeks, source_accession) rows for one fiscal year,
    from reported quarterly contexts inside the reported annual window.

    Q4 is rarely a reported context (there is no standalone Q4 filing); it is the
    CLOSURE of the reported year after reported Q3 — set difference of reported
    boundaries, not a calendar formula (DECISIONS.md #9).
    """
    fy_start, fy_end = fy_window
    acceptance = corpus_acceptance or {}

    def first_reporter(start: date, end: date) -> str:
        candidates = {e.accession for e in entries if e.period_start == start and e.period_end == end}
        in_corpus = [a for a in candidates if a in acceptance]
        if in_corpus:  # earliest corpus filing that reported this exact context
            return min(in_corpus, key=lambda a: acceptance[a])
        return min(candidates)

    candidates = sorted(
        {
            (e.period_start, e.period_end)
            for e in entries
            if e.period_start
            and fy_start <= e.period_start
            and e.period_end <= fy_end
            and (e.period_end - e.period_start).days in _QUARTER_DAYS
        }
    )

    def chain(cursor: date, picked: list[tuple[date, date]]):
        """DFS over reported contexts: 4 contiguous quarters covering the FY, or 3
        reported + a quarter-length remainder (Q4 closure — no standalone Q4 filing)."""
        if len(picked) == 4:
            return picked if cursor == fy_end + timedelta(days=1) else None
        for start, end in (c for c in candidates if c[0] == cursor):
            result = chain(end + timedelta(days=1), picked + [(start, end)])
            if result:
                return result
        if len(picked) == 3 and (fy_end - cursor).days in _QUARTER_DAYS:
            return picked + [(cursor, fy_end)]
        return None

    chained = chain(fy_start, [])
    if chained is None:
        raise FactsLoadError(
            f"FY {fy_start}→{fy_end}: no contiguous quarter chain in reported contexts "
            f"({len(candidates)} candidates)"
        )
    rows = []
    for index, (start, end) in enumerate(chained, start=1):
        reported = (start, end) in candidates
        witness = first_reporter(start, end) if reported else first_reporter(fy_start, fy_end)
        rows.append((f"Q{index}", start, end, witness))
    rows.append(("FY", fy_start, fy_end, first_reporter(fy_start, fy_end)))

    out = []
    for period, start, end, accession in rows:
        weeks = None
        if week_based:
            span = (end - start).days + 1
            if span % 7:
                raise FactsLoadError(f"{period} {start}→{end}: not whole weeks on a 52/53 calendar")
            weeks = span // 7
            expected = {52, 53} if period == "FY" else _QUARTER_WEEKS
            if weeks not in expected:
                raise FactsLoadError(f"{period} {start}→{end}: implausible {weeks} weeks")
        out.append((period, start, end, weeks, accession))
    return out


def upsert_calendar(
    conn: psycopg.Connection,
    company_id: int,
    fiscal_year: int,
    rows: list[tuple[str, date, date, int | None, str]],
    corpus_acceptance: dict[str, datetime],
) -> None:
    for period, start, end, weeks, accession in rows:
        existing = conn.execute(
            "SELECT period_start, period_end, source FROM fiscal_calendars"
            " WHERE company_id = %s AND fiscal_year = %s AND fiscal_period = %s",
            (company_id, fiscal_year, period),
        ).fetchone()
        if existing and (existing[0], existing[1]) != (start, end):
            raise FactsLoadError(
                f"FY{fiscal_year} {period}: XBRL says {start}→{end}, "
                f"{existing[2]} row says {existing[0]}→{existing[1]} — "
                "resolve by hand, never overwrite (U8)"
            )
        conn.execute(
            """
            INSERT INTO fiscal_calendars (company_id, fiscal_year, fiscal_period,
                period_start, period_end, weeks, source, source_accession, knowledge_time)
            VALUES (%s, %s, %s, %s, %s, %s, 'xbrl', %s, %s)
            ON CONFLICT (company_id, fiscal_year, fiscal_period) DO UPDATE
                SET weeks = COALESCE(fiscal_calendars.weeks, EXCLUDED.weeks),
                    source = 'xbrl',
                    source_accession = EXCLUDED.source_accession,
                    knowledge_time = EXCLUDED.knowledge_time
            """,
            (
                company_id,
                fiscal_year,
                period,
                start,
                end,
                weeks,
                accession,
                corpus_acceptance.get(accession),
            ),
        )


# ---------- supersession pass (U11) ----------


def supersession_pass(conn: psycopg.Connection, company_id: int) -> list[tuple[int, int]]:
    """Link every older, still-authoritative row to the newest row that re-reports
    its identity with a DIFFERENT value. Returns the (old, new) pairs made."""
    groups: dict[tuple, list] = defaultdict(list)
    # 8K-EX99 rows join the identity groups so a later 10-Q re-reporting a
    # DIFFERENT value supersedes the preliminary row (design §4.2 wrinkle 1);
    # 'derived' rows never participate (they are recomputed, not reported)
    for fact_id, concept, unit, p_start, p_end, value, knowledge_time, superseded_by in conn.execute(
        "SELECT fact_id, concept, unit, period_start, period_end, value,"
        " knowledge_time, superseded_by FROM facts"
        " WHERE company_id = %s AND axis IS NULL"
        " AND source IN ('10-K', '10-Q', '8K-EX99')"
        " ORDER BY knowledge_time, fact_id",
        (company_id,),
    ):
        groups[(concept, unit, p_start, p_end)].append(
            {"id": fact_id, "value": value, "kt": knowledge_time, "sup": superseded_by}
        )
    links = []
    for rows in groups.values():
        for i, newer in enumerate(rows):
            for older in rows[:i]:
                if older["sup"] is None and older["value"] != newer["value"]:
                    supersede(conn, older["id"], newer["id"])
                    older["sup"] = newer["id"]
                    links.append((older["id"], newer["id"]))
    return links


# ---------- per-company driver ----------


def load_company(conn: psycopg.Connection, ticker: str) -> dict:
    company_id, cik, week_based = conn.execute(
        "SELECT company_id, cik, week_52_53_calendar FROM companies c"
        " JOIN tickers t USING (company_id) WHERE t.ticker = %s",
        (ticker,),
    ).fetchone()
    companyfacts = load_companyfacts(cik)
    entries = iter_entries(companyfacts)
    corpus_acceptance = _corpus_acceptance(conn, company_id)
    if not corpus_acceptance:
        raise FactsLoadError(f"{ticker}: no corpus documents registered — run the backfill first")
    filings = {f.accession: f for f in load_cached_submissions(cik)}

    rows, baselines, skipped = select_rows(entries, corpus_acceptance, filings)
    from us_rag.ingest.backfill import register  # late import avoids a cycle at module load

    for filing in baselines:
        register(conn, company_id, filing, corpus=False, status="metadata")

    inserted = insert_rows(conn, company_id, rows)

    windows = annual_windows(companyfacts)
    for fiscal_year in CORPUS_FISCAL_YEARS:
        calendar_rows = derive_calendar(
            entries,
            windows[fiscal_year],
            week_based=week_based,
            corpus_acceptance=corpus_acceptance,
        )
        upsert_calendar(conn, company_id, fiscal_year, calendar_rows, corpus_acceptance)

    links = supersession_pass(conn, company_id)
    conn.commit()
    return {
        "ticker": ticker,
        "facts_inserted": inserted,
        "baseline_documents": len(baselines),
        "skipped_unresolvable": skipped,
        "supersessions": len(links),
    }


def main(tickers: list[str] | None = None) -> list[dict]:
    from us_rag.env import repo_root

    universe = [
        entry["ticker"] for entry in json.loads((repo_root() / "universe.json").read_text())
    ]
    summaries = []
    with connect() as conn:
        for ticker in tickers or universe:
            summary = load_company(conn, ticker)
            summaries.append(summary)
            print(json.dumps(summary))
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load companyfacts into the facts store")
    parser.add_argument("--tickers", nargs="*")
    main(parser.parse_args().tickers)
