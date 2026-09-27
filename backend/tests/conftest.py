"""Test DB: dropped and rebuilt from migrations + seeds each session — every pytest
run is also a from-scratch migration test. Tests never commit; the function-scoped
`conn` rolls back, so tests are isolated without violating the append-only trigger."""

from __future__ import annotations

import psycopg
import pytest

from us_rag.db import database_url
from us_rag.store.migrate import migrate
from us_rag.store.seed import seed_fiscal_calendars, seed_security_master

TEST_DB = "usrag_test"


@pytest.fixture(scope="session")
def db_url() -> str:
    base = database_url()
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    url = base.rsplit("/", 1)[0] + f"/{TEST_DB}"
    migrate(url)
    seed_security_master(url)
    seed_fiscal_calendars(url)
    return url


@pytest.fixture
def conn(db_url: str):
    connection = psycopg.connect(db_url)
    yield connection
    connection.rollback()
    connection.close()


@pytest.fixture
def company_id(conn):
    """company_id lookup helper: company_id('NVDA')."""

    def lookup(ticker: str) -> int:
        row = conn.execute(
            "SELECT company_id FROM tickers WHERE ticker = %s", (ticker,)
        ).fetchone()
        assert row, f"ticker {ticker} not seeded"
        return row[0]

    return lookup


def pytest_collection_modifyitems(config, items):
    """A test that touches the database — directly via `db_url`, or through `conn` /
    `company_id`, which depend on it — is an *integration* test; everything else is a
    *unit* test that runs with no services. Marking by fixture keeps the split automatic:
    a new DB test is classified correctly without anyone remembering a marker."""
    for item in items:
        if "db_url" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.integration)
