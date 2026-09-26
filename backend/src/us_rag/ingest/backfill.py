"""Backfill (plan 2a): the full U2 corpus fetched to blobs/ and registered.

Corpus selection per company (ADR-0020):
- periodic filings (10-K/10-Q and their /A amendments): report period end inside
  [FY2024 start, FY2025 end], where the boundaries come from the company's OWN
  annual XBRL contexts in companyfacts (FY label = calendar year containing the
  period end, design §4.6), cross-checked against the fiscal seeds — a mismatch
  is a hard error, never silently resolved;
- event filings (8-K and /A): accepted between FY2024 start and the FY2025 10-K
  acceptance — the filing that closes the corpus. A pure period-window cut would
  miss the Q4 FY2025 earnings release, which lands AFTER fiscal year end and is
  the U13 workhorse.

Idempotent by accession: a documents row already status='fetched' whose blob is
on disk is never refetched — rerun freely after any crash.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import psycopg

from us_rag.db import connect
from us_rag.env import repo_root
from us_rag.ingest.edgar import (
    EdgarClient,
    Filing,
    archive_url,
    companyfacts_url,
    write_limiter_stats,
)

BLOBS = repo_root() / "blobs"
STATS_PATH = BLOBS / "_edgar_stats.json"

FORMS_PERIODIC = {"10-K", "10-Q", "10-K/A", "10-Q/A"}
FORMS_EVENT = {"8-K", "8-K/A"}
CORPUS_FISCAL_YEARS = (2024, 2025)  # pin U2

# annual XBRL duration contexts; validation bounds, not derivation (cf. phase_01 gate)
_FY_DAYS = range(360, 373)


class CorpusError(RuntimeError):
    """The corpus cannot be assembled unambiguously — fail closed."""


@dataclass(frozen=True)
class CorpusSelection:
    fy_start: date  # FY2024 period start
    fy_end: date  # FY2025 period end
    close: date  # acceptance date of the FY2025 10-K — corpus close
    periodic: list[Filing]
    events: list[Filing]


def annual_windows(companyfacts: dict) -> dict[int, tuple[date, date]]:
    """FY label → (start, end) from the company's own reported annual contexts.

    We take actually-reported 10-K duration contexts of annual length and label
    them by the design §4.6 convention. Ties are broken by frequency — the same
    window is re-reported as a comparative many times; a typo context is not.
    """
    votes: Counter[tuple[int, date, date]] = Counter()
    for concept in companyfacts.get("facts", {}).get("us-gaap", {}).values():
        for entries in concept.get("units", {}).values():
            for entry in entries:
                if entry.get("form") not in ("10-K", "10-K/A"):
                    continue
                start, end = entry.get("start"), entry.get("end")
                if not start or not end:
                    continue
                start_d, end_d = date.fromisoformat(start), date.fromisoformat(end)
                if (end_d - start_d).days not in _FY_DAYS:
                    continue
                votes[(end_d.year, start_d, end_d)] += 1
    windows: dict[int, tuple[date, date]] = {}
    for label in sorted({label for label, _, _ in votes}):
        candidates = [(n, s, e) for (lbl, s, e), n in votes.items() if lbl == label]
        candidates.sort(reverse=True)  # most-voted window wins
        windows[label] = (candidates[0][1], candidates[0][2])
    return windows


def corpus_bounds(conn: psycopg.Connection, company_id: int, companyfacts: dict) -> tuple[date, date]:
    """[FY2024 start, FY2025 end] for one company, seed-cross-checked (gate rule)."""
    windows = annual_windows(companyfacts)
    for fy in CORPUS_FISCAL_YEARS:
        if fy not in windows:
            raise CorpusError(f"no annual XBRL context found for FY{fy}")
        seed = conn.execute(
            "SELECT period_start, period_end FROM fiscal_calendars"
            " WHERE company_id = %s AND fiscal_year = %s AND fiscal_period = 'FY'",
            (company_id, fy),
        ).fetchone()
        if seed and (seed[0], seed[1]) != windows[fy]:
            raise CorpusError(
                f"FY{fy} XBRL window {windows[fy]} != seed {tuple(seed)} — "
                "seed or derivation is wrong; resolve before ingesting (design §4.6)"
            )
    return windows[CORPUS_FISCAL_YEARS[0]][0], windows[CORPUS_FISCAL_YEARS[-1]][1]


def select_corpus(filings: list[Filing], fy_start: date, fy_end: date) -> CorpusSelection:
    periodic = [
        f
        for f in filings
        if f.form in FORMS_PERIODIC and f.report_date and fy_start <= f.report_date <= fy_end
    ]
    closing = [f for f in periodic if f.form == "10-K" and f.report_date == fy_end]
    if not closing:
        raise CorpusError(
            f"corpus incomplete: no 10-K reporting on {fy_end} — FY2025 not yet filed?"
        )
    close = min(f.acceptance for f in closing).date()
    events = [
        f for f in filings if f.form in FORMS_EVENT and fy_start <= f.acceptance.date() <= close
    ]
    return CorpusSelection(fy_start, fy_end, close, periodic, events)


# ---------- blob + registry plumbing ----------


def _cached_json(client: EdgarClient, path: Path, url: str, refresh: bool) -> dict:
    """Cache the RAW response text — a json round-trip would push exact XBRL
    decimals through Python floats (units.py rejects floats on principle)."""
    if not path.exists() or refresh:
        text = client.get(url).text
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return json.loads(path.read_text())


def companyfacts_path(cik: str) -> Path:
    return BLOBS / "companyfacts" / f"CIK{cik}.json"


def submissions_path(cik: str) -> Path:
    return BLOBS / "submissions" / f"CIK{cik}.json"


def load_cached_submissions(cik: str) -> list[Filing]:
    """Offline accessor for later stages (facts loader) — no client, no network."""
    from us_rag.ingest.edgar import _parse_filing_block

    pages = json.loads(submissions_path(cik).read_text())
    filings: list[Filing] = []
    for name, page in pages.items():
        block = page["filings"]["recent"] if name == "root" else page
        filings.extend(_parse_filing_block(block))
    return sorted(filings, key=lambda f: f.acceptance)


def register(
    conn: psycopg.Connection,
    company_id: int,
    filing: Filing,
    *,
    corpus: bool,
    status: str,
    primary_doc_url: str | None = None,
    blob_path: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO documents (accession, company_id, form, filed_date,
            acceptance_datetime, primary_doc_url, blob_path, status, corpus)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (accession) DO UPDATE
            SET status = EXCLUDED.status, blob_path = EXCLUDED.blob_path,
                primary_doc_url = EXCLUDED.primary_doc_url,
                corpus = documents.corpus OR EXCLUDED.corpus
        """,
        (
            filing.accession,
            company_id,
            filing.form,
            filing.filing_date,
            filing.acceptance,
            primary_doc_url,
            blob_path,
            status,
            corpus,
        ),
    )


def _already_fetched(conn: psycopg.Connection, accession: str) -> bool:
    row = conn.execute(
        "SELECT status, blob_path FROM documents WHERE accession = %s", (accession,)
    ).fetchone()
    return bool(row and row[0] == "fetched" and row[1] and (repo_root() / row[1]).exists())


def fetch_filing(
    client: EdgarClient,
    conn: psycopg.Connection,
    ticker: str,
    cik: str,
    company_id: int,
    filing: Filing,
) -> int:
    """Fetch one filing's primary document (+ EX-99 exhibits for 8-Ks) to blobs/.

    Returns the number of files downloaded (0 = was already fetched)."""
    if _already_fetched(conn, filing.accession):
        return 0
    folder = BLOBS / ticker / filing.accession
    folder.mkdir(parents=True, exist_ok=True)
    names = [filing.primary_document] if filing.primary_document else []
    exhibits: dict[str, str] = {}
    if filing.form in FORMS_EVENT:
        for exhibit_type, name in client.ex99_documents(cik, filing.accession):
            exhibits[Path(name).name] = exhibit_type
            if name not in names:
                names.append(name)
    if not names:
        raise CorpusError(f"{ticker} {filing.accession} ({filing.form}): no documents to fetch")
    for name in names:
        target = folder / Path(name).name
        if not target.exists():
            target.write_bytes(client.filing_file(cik, filing.accession, name))
    (folder / "_manifest.json").write_text(
        json.dumps({"primary": Path(names[0]).name, "exhibits": exhibits}, indent=2)
    )
    primary = names[0]
    register(
        conn,
        company_id,
        filing,
        corpus=True,
        status="fetched",
        primary_doc_url=archive_url(cik, filing.accession, primary),
        blob_path=str((folder / Path(primary).name).relative_to(repo_root())),
    )
    conn.commit()
    return len(names)


def backfill_company(
    client: EdgarClient,
    conn: psycopg.Connection,
    entry: dict,
    *,
    dry_run: bool = False,
    refresh: bool = False,
) -> dict:
    ticker, cik = entry["ticker"], entry["cik"]
    company_id = conn.execute(
        "SELECT company_id FROM companies WHERE cik = %s", (cik,)
    ).fetchone()[0]

    facts = _cached_json(client, companyfacts_path(cik), companyfacts_url(cik), refresh)
    fy_start, fy_end = corpus_bounds(conn, company_id, facts)

    sub_path = submissions_path(cik)
    if sub_path.exists() and not refresh:
        filings = load_cached_submissions(cik)
    else:
        filings, pages = client.all_filings(cik, back_to=fy_start)
        sub_path.parent.mkdir(parents=True, exist_ok=True)
        sub_path.write_text(json.dumps(pages))

    selection = select_corpus(filings, fy_start, fy_end)
    counts = Counter(f.form for f in selection.periodic + selection.events)
    summary = {
        "ticker": ticker,
        "window": [str(fy_start), str(fy_end)],
        "close": str(selection.close),
        "forms": dict(sorted(counts.items())),
        "downloaded_files": 0,
    }
    if dry_run:
        return summary
    for filing in selection.periodic + selection.events:
        summary["downloaded_files"] += fetch_filing(
            client, conn, ticker, cik, company_id, filing
        )
    return summary


def ensure_manifests(tickers: list[str] | None = None) -> int:
    """Repair pass: write _manifest.json for already-fetched 8-K folders that
    predate manifest support (one index-page request each)."""
    written = 0
    with EdgarClient() as client, connect() as conn:
        rows = conn.execute(
            "SELECT d.accession, d.form, c.cik, t.ticker FROM documents d"
            " JOIN companies c USING (company_id) JOIN tickers t USING (company_id)"
            " WHERE d.corpus AND d.status = 'fetched' ORDER BY t.ticker, d.accession",
        ).fetchall()
        for accession, form, cik, ticker in rows:
            if tickers and ticker not in tickers:
                continue
            folder = BLOBS / ticker / accession
            manifest = folder / "_manifest.json"
            if manifest.exists() or not folder.exists():
                continue
            exhibits = {}
            if form in FORMS_EVENT:
                exhibits = {
                    Path(name).name: exhibit_type
                    for exhibit_type, name in client.ex99_documents(cik, accession)
                }
            primary = conn.execute(
                "SELECT blob_path FROM documents WHERE accession = %s", (accession,)
            ).fetchone()[0]
            manifest.write_text(
                json.dumps({"primary": Path(primary).name, "exhibits": exhibits}, indent=2)
            )
            written += 1
        write_limiter_stats(client.limiter, STATS_PATH)
    return written


def backfill(tickers: list[str] | None = None, *, dry_run: bool = False, refresh: bool = False):
    universe = json.loads((repo_root() / "universe.json").read_text())
    if tickers:
        universe = [e for e in universe if e["ticker"] in tickers]
    summaries = []
    with EdgarClient() as client, connect() as conn:
        for entry in universe:
            summary = backfill_company(client, conn, entry, dry_run=dry_run, refresh=refresh)
            summaries.append(summary)
            print(json.dumps(summary))
        if not dry_run:
            write_limiter_stats(client.limiter, STATS_PATH)
            print(f"limiter: {client.limiter.stats()}")
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill the U2 corpus from EDGAR")
    parser.add_argument("--tickers", nargs="*", help="subset of tickers (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="select + count, no downloads")
    parser.add_argument("--refresh", action="store_true", help="refetch cached index JSONs")
    args = parser.parse_args()
    backfill(args.tickers, dry_run=args.dry_run, refresh=args.refresh)
