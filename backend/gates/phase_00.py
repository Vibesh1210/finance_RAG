"""Phase 0 gate: scaffold, services, universe fixtures.

Fixtures-only: no external data-API calls. The DB check talks to the local/CI
postgres service — infrastructure, not data fetching.
"""

import json
import os
import re

from common import ROOT, run_gate

from us_rag.env import load_env
from us_rag.universe import build_universe

REQUIRED_FILES = [
    "docker-compose.yml",
    "Makefile",
    "CLAUDE.md",
    "START_HERE.md",
    ".env.example",
    "README.md",
    "pyproject.toml",
    "docs/production/README.md",
    "docs/production/adr/README.md",
    "docs/learning_docs/00_how_to_understand_this_project.md",
    "docs/implementation/status.md",
    "docs/implementation/roadmap.md",
    "docs/implementation/archive/design_us.md",
    "docs/implementation/archive/execution_plan_us.md",
    "backend/db/init/01_extensions.sql",
    ".github/workflows/ci.yml",
    "fixtures/company_tickers.json",
    "universe.json",
]


def check_required_files() -> None:
    missing = [p for p in REQUIRED_FILES if not (ROOT / p).exists()]
    if missing:
        raise AssertionError(f"missing: {missing}")


def check_user_agent() -> None:
    load_env()
    ua = os.environ.get("SEC_EDGAR_USER_AGENT", "")
    if "@" not in ua:
        raise AssertionError(
            "SEC_EDGAR_USER_AGENT must be set (.env or env) and contain a contact "
            "email — EDGAR fair-access requirement (design §3.1)"
        )


def check_db_and_pgvector() -> None:
    import psycopg

    load_env()
    url = os.environ.get("DATABASE_URL", "postgresql://usrag:usrag@localhost:5433/usrag")
    with psycopg.connect(url, connect_timeout=5) as conn:
        row = conn.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'").fetchone()
    if row is None:
        raise AssertionError("pgvector extension not installed (run `make up`; see backend/db/init/)")


def check_universe_derivation() -> None:
    expected = build_universe(ROOT / "fixtures" / "company_tickers.json")
    actual = (ROOT / "universe.json").read_text()
    if actual != expected:
        raise AssertionError(
            "universe.json is not byte-identical to its derivation from the snapshot "
            "(regenerate: uv run python backend/scripts/build_universe.py; never hand-edit)"
        )


def check_universe_integrity() -> None:
    entries = json.loads((ROOT / "universe.json").read_text())
    if len(entries) != 10:
        raise AssertionError(f"expected 10 companies (U1), got {len(entries)}")
    for entry in entries:
        if not re.fullmatch(r"\d{10}", entry["cik"]):
            raise AssertionError(f"{entry['ticker']}: CIK not zero-padded to 10: {entry['cik']}")


run_gate(
    "phase_00",
    [
        ("repo scaffold files present", check_required_files),
        ("SEC_EDGAR_USER_AGENT configured with contact email", check_user_agent),
        ("postgres reachable + pgvector extension installed", check_db_and_pgvector),
        ("universe.json byte-identical to snapshot derivation", check_universe_derivation),
        ("universe.json: 10 companies, zero-padded CIKs", check_universe_integrity),
    ],
)
