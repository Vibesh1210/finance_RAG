"""Phase 1 gate: data spine — schemas, bitemporal facts, units, fiscal, identity.

Fixtures-only: talks to the local/CI postgres and the repo; no external data APIs.
"""

import re
import subprocess
import sys
from datetime import date, datetime, timezone

from common import ROOT, run_gate

from us_rag.db import connect
from us_rag.store.migrate import migrate
from us_rag.store.seed import seed_fiscal_calendars, seed_security_master

SRC = ROOT / "src" / "us_rag"


def check_migrations_apply_and_idempotent() -> None:
    migrate()
    second = migrate()
    if second:
        raise AssertionError(f"migrations not idempotent; second run applied {second}")


def check_seeds_load() -> None:
    seed_security_master()
    seed_fiscal_calendars()
    seed_security_master()  # idempotency
    seed_fiscal_calendars()


def check_pytest_suite() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-25:])
        raise AssertionError(f"pytest failed:\n{tail}")


def check_u8_no_formula_lint() -> None:
    fiscal_src = (SRC / "fiscal.py").read_text()
    for banned in ("timedelta(", "relativedelta", "dateutil", "days=9"):
        if banned in fiscal_src:
            raise AssertionError(f"U8 lint: {banned!r} found in fiscal.py — no period formulas")
    for path in SRC.rglob("*.py"):
        if "dateutil" in path.read_text():
            raise AssertionError(f"U8 lint: dateutil import in {path}")


def check_append_only_source_lint() -> None:
    update_hits, bad = [], []
    for path in SRC.rglob("*.py"):
        text = path.read_text()
        if re.search(r"UPDATE\s+facts", text, re.IGNORECASE):
            update_hits.append(path.name)
        if re.search(r"DELETE\s+FROM\s+facts|TRUNCATE", text, re.IGNORECASE):
            bad.append(path.name)
    if bad:
        raise AssertionError(f"append-only lint: DELETE/TRUNCATE on facts in {bad}")
    if update_hits != ["asof.py"]:
        raise AssertionError(
            f"append-only lint: 'UPDATE facts' must appear only in store/asof.py "
            f"(supersede); found in {update_hits}"
        )


def check_trigger_live() -> None:
    import psycopg

    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_trigger WHERE tgname = 'facts_append_only'"
        ).fetchone()
        if row is None:
            raise AssertionError("facts_append_only trigger missing")
        cid = conn.execute("SELECT company_id FROM companies LIMIT 1").fetchone()
        if cid is None:
            raise AssertionError("no seeded companies for the trigger probe")
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        conn.execute(
            "INSERT INTO documents (accession, company_id, form, filed_date,"
            " acceptance_datetime) VALUES ('GATE-PROBE', %s, '10-Q', %s, %s)",
            (cid[0], now.date(), now),
        )
        fid = conn.execute(
            "INSERT INTO facts (company_id, concept, value, unit, period_start,"
            " period_end, period_kind, knowledge_time, accession, source)"
            " VALUES (%s, 'Revenues', 1, 'USD', '2023-10-01', '2023-12-31',"
            " 'duration', %s, 'GATE-PROBE', '10-Q') RETURNING fact_id",
            (cid[0], now),
        ).fetchone()[0]
        for statement in (
            f"UPDATE facts SET value = 2 WHERE fact_id = {fid}",
            f"DELETE FROM facts WHERE fact_id = {fid}",
        ):
            try:
                with conn.transaction():
                    conn.execute(statement)
                raise AssertionError(f"append-only trigger did NOT block: {statement}")
            except psycopg.errors.RaiseException:
                pass  # blocked, as required
        conn.rollback()  # discard the probe rows entirely


def check_fiscal_seed_sanity() -> None:
    with connect() as conn:
        nvda = conn.execute(
            "SELECT count(*) FROM fiscal_calendars fc JOIN tickers t USING (company_id)"
            " WHERE t.ticker = 'NVDA' AND fc.fiscal_year = 2025"
        ).fetchone()[0]
        if nvda != 5:
            raise AssertionError(f"NVDA FY2025 must have FY+Q1..Q4 (5 rows), got {nvda}")
        de = conn.execute(
            "SELECT weeks FROM fiscal_calendars fc JOIN tickers t USING (company_id)"
            " WHERE t.ticker = 'DE' AND fc.fiscal_year = 2025 AND fc.fiscal_period = 'FY'"
        ).fetchone()
        if de != (53,):
            raise AssertionError(f"DE FY2025 must be the 53-week candidate, got {de}")
        # duration sanity is VALIDATION of stored rows (allowed) — not derivation (banned)
        bad_q = conn.execute(
            "SELECT count(*) FROM fiscal_calendars WHERE fiscal_period != 'FY'"
            " AND (period_end - period_start) NOT BETWEEN 83 AND 111"
        ).fetchone()[0]
        bad_fy = conn.execute(
            "SELECT count(*) FROM fiscal_calendars WHERE fiscal_period = 'FY'"
            " AND (period_end - period_start) NOT BETWEEN 360 AND 372"
        ).fetchone()[0]
        if bad_q or bad_fy:
            raise AssertionError(f"implausible seed durations: {bad_q} quarters, {bad_fy} years")


def check_resolver_canary() -> None:
    from us_rag.entities import resolve_one
    from us_rag.fiscal import resolve

    with connect() as conn:
        nvda = resolve_one(conn, "NVDA")
        res = resolve(conn, nvda.company_id, "NVDA", "Q3 FY2025")
        if res.period_end != date(2024, 10, 27):
            raise AssertionError(f"NVDA Q3 FY2025 resolved to {res.period_end}")
        if resolve_one(conn, "XOM").cik != "0000034088":
            raise AssertionError("XOM must resolve to the predecessor CIK (ADR-0004)")


run_gate(
    "phase_01",
    [
        ("migrations apply cleanly and idempotently", check_migrations_apply_and_idempotent),
        ("security-master + fiscal seeds load idempotently", check_seeds_load),
        ("U8 lint: no period formulas in fiscal.py", check_u8_no_formula_lint),
        ("append-only lint: no UPDATE/DELETE/TRUNCATE on facts outside supersede", check_append_only_source_lint),
        ("append-only trigger blocks UPDATE and DELETE (live probe)", check_trigger_live),
        ("fiscal seeds: NVDA FY2025 complete, DE FY2025 53wk, plausible durations", check_fiscal_seed_sanity),
        ("canary: NVDA Q3 FY2025 → 2024-10-27; XOM → predecessor CIK", check_resolver_canary),
        ("unit + fiscal + bitemporal + entity test suite green", check_pytest_suite),
    ],
)
