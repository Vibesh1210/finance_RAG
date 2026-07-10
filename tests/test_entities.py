"""Entity resolution: ticker/alias → company; ambiguity surfaced, never guessed."""

from datetime import date

import pytest

from us_rag.entities import UnknownEntityError, resolve, resolve_one


def test_ticker_resolution(conn):
    assert resolve_one(conn, "NVDA").cik == "0001045810"


def test_alias_case_insensitive(conn):
    assert resolve_one(conn, "nvidia").cik == "0001045810"
    assert resolve_one(conn, "Walmart").cik == "0000104169"


def test_full_sec_name(conn):
    assert resolve_one(conn, "Apple Inc.").cik == "0000320193"


def test_xom_resolves_to_predecessor_cik(conn):
    # DECISIONS.md #4: the filing entity, not the 2026-07-01 successor registrant
    assert resolve_one(conn, "XOM").cik == "0000034088"


def test_point_in_time_ticker(conn):
    assert resolve_one(conn, "XOM", as_of=date(2024, 6, 28)).cik == "0000034088"


def test_unknown_entity(conn):
    with pytest.raises(UnknownEntityError, match="no company matches"):
        resolve_one(conn, "TSLA")


def test_ambiguity_is_surfaced_not_guessed(conn):
    ids = [row[0] for row in conn.execute("SELECT company_id FROM companies LIMIT 2")]
    for cid in ids:  # same alias on two companies, inside the rolled-back test txn
        conn.execute(
            "INSERT INTO name_aliases (company_id, alias) VALUES (%s, 'Apex')", (cid,)
        )
    assert len(resolve(conn, "Apex")) == 2
    with pytest.raises(UnknownEntityError, match="ambiguous"):
        resolve_one(conn, "Apex")
