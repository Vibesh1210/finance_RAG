"""Bitemporal semantics (design §4.2, U11) on synthetic rows: as-of visibility,
supersession chains, the preliminary 8-K window, and append-only enforcement."""

from datetime import date, datetime, timezone
from decimal import Decimal

import psycopg
import pytest

from us_rag.store.asof import AsOfContext, insert_fact, supersede

T0 = datetime(2024, 8, 1, tzinfo=timezone.utc)
T1 = datetime(2024, 8, 28, 21, 5, tzinfo=timezone.utc)   # 8-K acceptance
T1_5 = datetime(2024, 9, 15, tzinfo=timezone.utc)
T2 = datetime(2024, 10, 30, 16, 1, tzinfo=timezone.utc)  # 10-Q acceptance
T3 = datetime(2025, 2, 26, tzinfo=timezone.utc)


@pytest.fixture
def nvda(conn, company_id):
    return company_id("NVDA")


def make_doc(conn, cid, accession, form, accepted):
    conn.execute(
        "INSERT INTO documents (accession, company_id, form, filed_date,"
        " acceptance_datetime) VALUES (%s, %s, %s, %s, %s)",
        (accession, cid, form, accepted.date(), accepted),
    )


def make_fact(conn, cid, accession, kt, value, *, source="10-Q", preliminary=False,
              concept="Revenues", verified=False):
    return insert_fact(
        conn,
        company_id=cid, concept=concept, axis=None, member=None,
        value=Decimal(value), unit="USD",
        period_start=date(2024, 7, 29), period_end=date(2024, 10, 27),
        period_kind="duration", knowledge_time=kt, accession=accession,
        source=source, preliminary=preliminary, human_verified=verified,
    )


@pytest.fixture
def preliminary_then_final(conn, nvda):
    """The canonical 8-K → 10-Q pair with a value revision."""
    make_doc(conn, nvda, "TEST-8K-1", "8-K", T1)
    make_doc(conn, nvda, "TEST-10Q-1", "10-Q", T2)
    prelim = make_fact(conn, nvda, "TEST-8K-1", T1, "35082000000",
                       source="8K-EX99", preliminary=True, verified=True)
    final = make_fact(conn, nvda, "TEST-10Q-1", T2, "35082000001")
    supersede(conn, prelim, final)
    return prelim, final


def test_asof_windows(conn, nvda, preliminary_then_final):
    prelim, final = preliminary_then_final
    assert AsOfContext(conn, T0).facts(company_id=nvda) == []
    in_window = AsOfContext(conn, T1_5).facts(company_id=nvda)
    assert [f["fact_id"] for f in in_window] == [prelim]
    assert in_window[0]["preliminary"] is True and in_window[0]["source"] == "8K-EX99"
    after = AsOfContext(conn, T3).facts(company_id=nvda)
    assert [f["fact_id"] for f in after] == [final]


def test_supersession_chain(conn, nvda):
    make_doc(conn, nvda, "TEST-A", "10-Q", T1)
    make_doc(conn, nvda, "TEST-B", "10-Q", T2)
    make_doc(conn, nvda, "TEST-C", "10-K", T3)
    a = make_fact(conn, nvda, "TEST-A", T1, "100")
    b = make_fact(conn, nvda, "TEST-B", T2, "110")
    c = make_fact(conn, nvda, "TEST-C", T3, "120")
    supersede(conn, a, b)
    supersede(conn, b, c)
    for as_of, visible in [(T1, a), (T1_5, a), (T2, b), (T3, c)]:
        rows = AsOfContext(conn, as_of).facts(company_id=nvda)
        assert [f["fact_id"] for f in rows] == [visible]


def test_update_blocked_by_trigger(conn, nvda):
    make_doc(conn, nvda, "TEST-U", "10-Q", T1)
    fid = make_fact(conn, nvda, "TEST-U", T1, "100")
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        with conn.transaction():
            conn.execute("UPDATE facts SET value = 999 WHERE fact_id = %s", (fid,))


def test_delete_blocked_by_trigger(conn, nvda):
    make_doc(conn, nvda, "TEST-D", "10-Q", T1)
    fid = make_fact(conn, nvda, "TEST-D", T1, "100")
    with pytest.raises(psycopg.errors.RaiseException, match="DELETE forbidden"):
        with conn.transaction():
            conn.execute("DELETE FROM facts WHERE fact_id = %s", (fid,))


def test_double_supersession_blocked(conn, nvda):
    make_doc(conn, nvda, "TEST-DS", "10-Q", T1)
    a = make_fact(conn, nvda, "TEST-DS", T1, "100")
    b = make_fact(conn, nvda, "TEST-DS", T2, "110")
    c = make_fact(conn, nvda, "TEST-DS", T3, "120")
    supersede(conn, a, b)
    with pytest.raises(psycopg.errors.RaiseException, match="already superseded"):
        with conn.transaction():
            supersede(conn, a, c)


def test_supersede_requires_same_logical_fact(conn, nvda):
    make_doc(conn, nvda, "TEST-ID", "10-Q", T1)
    a = make_fact(conn, nvda, "TEST-ID", T1, "100", concept="Revenues")
    b = make_fact(conn, nvda, "TEST-ID", T2, "110", concept="NetIncomeLoss")
    with pytest.raises(ValueError, match="not the same logical fact"):
        supersede(conn, a, b)


def test_supersede_rejects_time_travel(conn, nvda):
    make_doc(conn, nvda, "TEST-TT", "10-Q", T2)
    a = make_fact(conn, nvda, "TEST-TT", T2, "100")
    b = make_fact(conn, nvda, "TEST-TT", T1, "110")
    with pytest.raises(ValueError, match="known earlier"):
        supersede(conn, a, b)


def test_chunks_respect_as_of(conn, nvda):
    make_doc(conn, nvda, "TEST-CH", "10-Q", T2)
    conn.execute(
        "INSERT INTO chunks (accession, company_id, doc_type, section, knowledge_time, text)"
        " VALUES ('TEST-CH', %s, '10-Q', 'Item 2', %s, 'Data Center revenue grew.')",
        (nvda, T2),
    )
    assert AsOfContext(conn, T1).chunks(company_id=nvda) == []
    assert len(AsOfContext(conn, T2).chunks(company_id=nvda)) == 1
