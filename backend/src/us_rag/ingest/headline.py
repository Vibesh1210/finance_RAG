"""U13 headline extraction (plan 2e): 8-K Item 2.02 press releases → three
preliminary facts each (revenue, net income, diluted EPS), 100% human-gated.

The division of labor is the whole design (pins U13 + no-LLM-arithmetic):
- The LLM READS: it copies the numbers verbatim with their source sentences.
  It never computes, never converts units, never fills gaps.
- The CODE normalizes: units.parse_quantity, fail-closed — a number whose scale
  is not stated in its own sentence is rejected, never guessed.
- The HUMAN verifies: every staged row is checked against the actual release
  before it may be inserted ([HUMAN], ~1.5–2 h for ~80 releases).

Workflow:
  1. python -m us_rag.ingest.headline extract   → writes fixtures/u13_staged.json
     (requires GEMINI_API_KEY — free tier suffices; model from GEMINI_MODEL)
  2. [HUMAN] reviews every row against the release; sets "verified": true
     (corrections: fix value_text/quote from the release, leave verified false,
     rerun `normalize` to recompute, then verify)
  3. python -m us_rag.ingest.headline normalize → recompute value_usd from
     value_text after human edits
  4. python -m us_rag.ingest.headline insert    → facts rows, source='8K-EX99',
     preliminary=TRUE, human_verified=TRUE at insert (the append-only trigger
     forbids post-insert flag flips — ADR-0005), knowledge_time = the
     8-K acceptance datetime.

Rows are keyed (accession, concept): extract and insert are both idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from decimal import Decimal

import psycopg

from us_rag.db import connect
from us_rag.env import load_env, repo_root
from us_rag.ingest.narrative import blocks_from_html
from us_rag.units import UnitError, parse_quantity

STAGED_PATH = repo_root() / "fixtures" / "u13_staged.json"
MAX_RELEASE_CHARS = 24_000  # headline numbers live in the first pages

METRICS = {
    # metric → (facts.concept, unit, parse metric_class)
    "revenue": ("Revenues", "USD", "currency"),
    "net_income": ("NetIncomeLoss", "USD", "currency"),
    "diluted_eps": ("EarningsPerShareDiluted", "USD/shares", "per_share"),
}

PROMPT = """You are extracting three headline numbers from an earnings press release.

Company: {ticker}. The release announces results for the fiscal quarter that ended {period_end}.

Extract, FOR THAT QUARTER ONLY (not the full year, not YTD, not prior periods, GAAP not adjusted/non-GAAP):
1. revenue (total revenue / net sales / total net revenue)
2. net_income (GAAP net income attributable to the company)
3. diluted_eps (GAAP diluted earnings per share)

Rules — these are hard rules:
- Copy each number VERBATIM as printed, including its unit words (e.g. "$30.04 billion", "$14,881 million", "6.13"). Do not convert, compute, or round anything.
- quote = the complete sentence or table line the number appears in, verbatim.
- If a value is genuinely not stated for the quarter, use null and say why in "note".
- Answer with ONLY a JSON object, no prose:

{{"revenue": {{"value_text": "...", "quote": "..."}} | null,
  "net_income": {{"value_text": "...", "quote": "..."}} | null,
  "diluted_eps": {{"value_text": "...", "quote": "..."}} | null,
  "note": "..."}}

Press release text:
{text}
"""


def select_releases(conn: psycopg.Connection) -> list[dict]:
    """Corpus 8-Ks with Item 2.02 and an EX-99.1 exhibit, with the fiscal quarter
    they announce (the company's latest quarter completed before acceptance) and
    the acceptance of the matching later periodic filing (gate check 7)."""
    from us_rag.ingest.backfill import load_cached_submissions

    releases = []
    companies = conn.execute(
        "SELECT company_id, cik, ticker FROM companies JOIN tickers USING (company_id)"
    ).fetchall()
    for company_id, cik, ticker in companies:
        items_by_accession = {
            f.accession: f.items for f in load_cached_submissions(cik)
        }
        rows = conn.execute(
            "SELECT accession, acceptance_datetime, blob_path FROM documents"
            " WHERE company_id = %s AND corpus AND form IN ('8-K', '8-K/A')"
            " ORDER BY acceptance_datetime",
            (company_id,),
        ).fetchall()
        for accession, acceptance, blob_path in rows:
            if "2.02" not in (items_by_accession.get(accession) or ""):
                continue
            folder = (repo_root() / blob_path).parent
            manifest = folder / "_manifest.json"
            if not manifest.exists():
                continue
            exhibits = json.loads(manifest.read_text())["exhibits"]
            ex991 = [
                name for name, ext_type in exhibits.items()
                if ext_type in ("EX-99.1", "EX-99.01", "EX-99")
            ]
            if not ex991:
                continue
            quarter = conn.execute(
                "SELECT fiscal_year, fiscal_period, period_start, period_end"
                " FROM fiscal_calendars WHERE company_id = %s AND fiscal_period != 'FY'"
                " AND period_end < %s::date ORDER BY period_end DESC LIMIT 1",
                (company_id, acceptance),
            ).fetchone()
            if quarter is None:
                continue  # release predates our calendar coverage
            following = conn.execute(
                "SELECT min(acceptance_datetime) FROM documents"
                " WHERE company_id = %s AND corpus AND form IN ('10-Q', '10-K')"
                " AND acceptance_datetime > %s",
                (company_id, acceptance),
            ).fetchone()[0]
            releases.append(
                {
                    "ticker": ticker,
                    "accession": accession,
                    "acceptance": acceptance.isoformat(),
                    "exhibit": ex991[0],
                    "exhibit_path": str((folder / ex991[0]).relative_to(repo_root())),
                    "fiscal_year": quarter[0],
                    "fiscal_period": quarter[1],
                    "period_start": str(quarter[2]),
                    "period_end": str(quarter[3]),
                    "next_periodic_acceptance": following.isoformat() if following else None,
                }
            )
    return releases


def release_text(exhibit_path: str) -> str:
    blocks = blocks_from_html((repo_root() / exhibit_path).read_bytes())
    return "\n".join(b.text for b in blocks)[:MAX_RELEASE_CHARS]


REQUEST_SPACING = 6.5  # seconds between calls — free tier allows 10 requests/min


def _llm_extract(release: dict) -> dict:
    from google import genai
    from google.genai import errors as genai_errors

    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError(
            "GEMINI_API_KEY is empty — [HUMAN] task: free key from"
            " https://aistudio.google.com into .env, then rerun"
        )
    client = genai.Client()  # reads GEMINI_API_KEY from the environment
    prompt = PROMPT.format(
        ticker=release["ticker"],
        period_end=release["period_end"],
        text=release_text(release["exhibit_path"]),
    )
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    for attempt in range(5):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            break
        except genai_errors.APIError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(30)  # free-tier rate limit or transient server error
                continue
            raise
    text = (response.text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return json.loads(text)


def normalize_value(metric: str, value_text: str) -> Decimal:
    """Deterministic, fail-closed: LLM text → exact Decimal. Bare scalable
    quantities ('30,040' with no scale words) are REJECTED, never guessed."""
    _, _, metric_class = METRICS[metric]
    return parse_quantity(value_text, metric_class=metric_class).value


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")  # '39300000000', never '3.93E+10' or '...0.0'


def stage_rows(release: dict, extraction: dict) -> list[dict]:
    rows = []
    for metric, (concept, unit, _) in METRICS.items():
        found = extraction.get(metric)
        row = {
            "ticker": release["ticker"],
            "accession": release["accession"],
            "acceptance": release["acceptance"],
            "exhibit_path": release["exhibit_path"],
            "fiscal": f"FY{release['fiscal_year']} {release['fiscal_period']}",
            "period_start": release["period_start"],
            "period_end": release["period_end"],
            "next_periodic_acceptance": release["next_periodic_acceptance"],
            "metric": metric,
            "concept": concept,
            "unit": unit,
            "verified": False,
        }
        if not found or not found.get("value_text"):
            row["error"] = f"not extracted: {extraction.get('note', 'no value returned')}"
        else:
            row["value_text"] = found["value_text"]
            row["quote"] = found.get("quote", "")
            try:
                row["value"] = _plain(normalize_value(metric, found["value_text"]))
            except UnitError as exc:
                row["error"] = f"normalizer rejected: {exc}"
        rows.append(row)
    return rows


def _load_staged() -> list[dict]:
    if STAGED_PATH.exists():
        return json.loads(STAGED_PATH.read_text())
    return []


def _write_staged(rows: list[dict]) -> None:
    STAGED_PATH.write_text(json.dumps(rows, indent=2) + "\n")


def cmd_extract() -> None:
    staged = _load_staged()
    have = {(r["accession"], r["metric"]) for r in staged}
    with connect() as conn:
        releases = select_releases(conn)
    print(f"{len(releases)} Item 2.02 releases with EX-99.1")
    for release in releases:
        if all((release["accession"], metric) in have for metric in METRICS):
            continue
        extraction = _llm_extract(release)
        rows = stage_rows(release, extraction)
        staged.extend(r for r in rows if (r["accession"], r["metric"]) not in have)
        _write_staged(staged)  # write-as-you-go: a crash loses nothing
        print(
            f"staged {release['ticker']} FY{release['fiscal_year']}"
            f" {release['fiscal_period']} ({release['accession']})"
        )
        time.sleep(REQUEST_SPACING)
    errors = [r for r in staged if "error" in r]
    print(f"staged total: {len(staged)} rows, {len(errors)} need attention")
    print(f"[HUMAN] next: verify every row in {STAGED_PATH.relative_to(repo_root())}")


def cmd_normalize() -> None:
    staged = _load_staged()
    for row in staged:
        if "value_text" in row:
            try:
                row["value"] = _plain(normalize_value(row["metric"], row["value_text"]))
                row.pop("error", None)
            except UnitError as exc:
                row["error"] = f"normalizer rejected: {exc}"
                row.pop("value", None)
    _write_staged(staged)
    print(f"renormalized {len(staged)} rows")


def cmd_insert() -> None:
    staged = _load_staged()
    unverified = [r for r in staged if not r.get("verified")]
    if unverified:
        sys.exit(
            f"REFUSING: {len(unverified)} staged rows are not verified — U13 requires "
            "100% human verification before insert (first unverified: "
            f"{unverified[0]['ticker']} {unverified[0]['fiscal']} {unverified[0]['metric']})"
        )
    inserted = skipped = 0
    from us_rag.store.asof import insert_fact

    with connect() as conn:
        existing = {
            tuple(row)
            for row in conn.execute(
                "SELECT accession, concept FROM facts WHERE source = '8K-EX99'"
            )
        }
        for row in staged:
            if (row["accession"], row["concept"]) in existing:
                skipped += 1
                continue
            value = Decimal(row["value"])
            if normalize_value(row["metric"], row["value_text"]) != value:
                sys.exit(f"staged value drifted from value_text: {row}")
            company_id = conn.execute(
                "SELECT company_id FROM tickers WHERE ticker = %s", (row["ticker"],)
            ).fetchone()[0]
            insert_fact(
                conn,
                company_id=company_id,
                concept=row["concept"],
                axis=None,
                member=None,
                value=value,
                unit=row["unit"],
                period_start=date.fromisoformat(row["period_start"]),
                period_end=date.fromisoformat(row["period_end"]),
                period_kind="duration",
                knowledge_time=datetime.fromisoformat(row["acceptance"]),
                accession=row["accession"],
                source="8K-EX99",
                preliminary=True,
                human_verified=True,  # verified BEFORE insert; the trigger forbids flips
            )
            inserted += 1
        conn.commit()
    print(f"inserted {inserted} preliminary facts ({skipped} already present)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="U13 headline extraction workflow")
    parser.add_argument("command", choices=["extract", "normalize", "insert", "list"])
    command = parser.parse_args().command
    if command == "extract":
        cmd_extract()
    elif command == "normalize":
        cmd_normalize()
    elif command == "insert":
        cmd_insert()
    else:
        with connect() as conn:
            for release in select_releases(conn):
                print(json.dumps(release))
