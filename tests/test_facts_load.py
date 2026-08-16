"""Facts loader tests (plan 2b), fixtures-only. The load-scope rule, the
fy/fp-independence hard rule, calendar derivation, and the supersession pass."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from us_rag.ingest.edgar import Filing
from us_rag.ingest.facts_load import (
    FactsLoadError,
    derive_calendar,
    insert_rows,
    iter_entries,
    select_rows,
    supersession_pass,
    upsert_calendar,
)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def _filing(accession: str, form: str, accepted: str, report: str | None = None) -> Filing:
    return Filing(
        accession=accession,
        form=form,
        filing_date=date.fromisoformat(accepted[:10]),
        report_date=date.fromisoformat(report) if report else None,
        acceptance=_dt(accepted),
        primary_document="doc.htm",
        items="",
    )


def _register(conn, company_id, filing, corpus=True):
    conn.execute(
        "INSERT INTO documents (accession, company_id, form, filed_date,"
        " acceptance_datetime, status, corpus) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (accession) DO NOTHING",
        (
            filing.accession,
            company_id,
            filing.form,
            filing.filing_date,
            filing.acceptance,
            "fetched" if corpus else "metadata",
            corpus,
        ),
    )


# ---------- fy/fp independence (hard rule a; gate check 8) ----------

LYING_COMPANYFACTS = {
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            # context dates say NVDA Q2 FY2025; fy/fp LIE on purpose.
                            "start": "2024-04-29",
                            "end": "2024-07-28",
                            "val": 30040000000,
                            "accn": "TEST-Q2-10Q",
                            "form": "10-Q",
                            "fy": 1999,
                            "fp": "Q9",
                            "filed": "2024-08-28",
                        }
                    ]
                }
            }
        }
    }
}


def test_fyfp_never_touch_period_identity(conn, company_id):
    nvda = company_id("NVDA")
    filing = _filing("TEST-Q2-10Q", "10-Q", "2024-08-28T16:31:22", "2024-07-28")
    _register(conn, nvda, filing)
    entries = iter_entries(LYING_COMPANYFACTS)
    rows, baselines, skipped = select_rows(
        entries, {"TEST-Q2-10Q": filing.acceptance}, {filing.accession: filing}
    )
    assert insert_rows(conn, nvda, rows) == 1
    loaded = conn.execute(
        "SELECT period_start, period_end, knowledge_time FROM facts"
        " WHERE accession = 'TEST-Q2-10Q'"
    ).fetchone()
    # dates win: the row's period is the context, and it joins to the seeded
    # fiscal calendar as Q2 FY2025 — the lying fy=1999/fp=Q9 left no trace
    assert (loaded[0], loaded[1]) == (date(2024, 4, 29), date(2024, 7, 28))
    assert loaded[2] == filing.acceptance
    resolved = conn.execute(
        "SELECT fiscal_year, fiscal_period FROM fiscal_calendars"
        " WHERE company_id = %s AND period_start = %s AND period_end = %s",
        (nvda, loaded[0], loaded[1]),
    ).fetchone()
    assert resolved == (2025, "Q2")


# ---------- load scope: corpus groups + as-reported-then baseline ----------


def _cf(entries: list[dict]) -> dict:
    return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": entries}}}}}


def test_select_rows_scopes_to_corpus_and_keeps_latest_baseline():
    entry = {"start": "2023-01-01", "end": "2023-12-31", "form": "10-K"}
    cf = _cf(
        [
            # original FY2023 number, reported twice pre-corpus (10-K then 10-K/A)
            {**entry, "val": 100, "accn": "PRE-1"},
            {**entry, "val": 100, "accn": "PRE-2", "form": "10-K/A"},
            # recast comparative inside the corpus 10-K
            {**entry, "val": 90, "accn": "CORP-1"},
            # a group nothing in the corpus reports — out of scope entirely
            {"start": "2010-01-01", "end": "2010-12-31", "val": 1, "accn": "PRE-1", "form": "10-K"},
        ]
    )
    filings = {
        "PRE-1": _filing("PRE-1", "10-K", "2024-02-10T16:00:00"),
        "PRE-2": _filing("PRE-2", "10-K/A", "2024-06-01T16:00:00"),
    }
    corpus = {"CORP-1": _dt("2025-02-20T16:00:00")}
    rows, baselines, skipped = select_rows(iter_entries(cf), corpus, filings)
    loaded = {(e.accession, e.value) for e, _ in rows}
    # corpus entry + the LATEST pre-corpus report only (the amendment, not the original)
    assert loaded == {("CORP-1", 90), ("PRE-2", 100)}
    assert [f.accession for f in baselines] == ["PRE-2"]
    assert skipped == 0


def test_select_rows_counts_unresolvable_ancients():
    entry = {"start": "2023-01-01", "end": "2023-12-31", "form": "10-K"}
    cf = _cf([{**entry, "val": 90, "accn": "CORP-1"}, {**entry, "val": 80, "accn": "ANCIENT"}])
    rows, baselines, skipped = select_rows(
        iter_entries(cf), {"CORP-1": _dt("2025-02-20T16:00:00")}, {}
    )
    assert {e.accession for e, _ in rows} == {"CORP-1"}
    assert skipped == 1


def test_iter_entries_rejects_contradictory_duplicates():
    entry = {"start": "2023-01-01", "end": "2023-12-31", "form": "10-K", "accn": "A"}
    with pytest.raises(FactsLoadError):
        iter_entries(_cf([{**entry, "val": 1}, {**entry, "val": 2}]))


def test_iter_entries_is_decimal_exact():
    cf = _cf(
        [{"start": "2023-01-01", "end": "2023-12-31", "val": Decimal("6.13"),
          "accn": "A", "form": "10-K"}]
    )
    (entry,) = iter_entries(cf)
    assert entry.value == Decimal("6.13")


# ---------- calendar derivation (pin U8; gate check 3) ----------

NVDA_FY25 = (date(2024, 1, 29), date(2025, 1, 26))


def _ctx(start: str, end: str, accn: str = "X") -> dict:
    return {"start": start, "end": end, "val": 1, "accn": accn, "form": "10-Q"}


def test_derive_calendar_closes_q4_and_counts_weeks():
    cf = _cf(
        [
            _ctx("2024-01-29", "2024-04-28", "q1"),
            _ctx("2024-04-29", "2024-07-28", "q2"),
            _ctx("2024-07-29", "2024-10-27", "q3"),
            {"start": "2024-01-29", "end": "2025-01-26", "val": 1, "accn": "fy", "form": "10-K"},
        ]
    )
    rows = derive_calendar(iter_entries(cf), NVDA_FY25, week_based=True)
    periods = {p: (s, e, w) for p, s, e, w, _ in rows}
    assert periods["Q4"] == (date(2024, 10, 28), date(2025, 1, 26), 13)
    assert periods["FY"][2] == 52
    assert set(periods) == {"Q1", "Q2", "Q3", "Q4", "FY"}


def test_derive_calendar_handles_costco_12_12_12_16():
    # COST FY2024: 12-week Q1..Q3, 16-week Q4 — the universe's proof that
    # "quarter" does not mean "13 weeks"
    fy = (date(2023, 9, 4), date(2024, 9, 1))
    cf = _cf(
        [
            _ctx("2023-09-04", "2023-11-26", "q1"),
            _ctx("2023-11-27", "2024-02-18", "q2"),
            _ctx("2024-02-19", "2024-05-12", "q3"),
            {"start": "2023-09-04", "end": "2024-09-01", "val": 1, "accn": "fy", "form": "10-K"},
        ]
    )
    rows = derive_calendar(iter_entries(cf), fy, week_based=True)
    periods = {p: w for p, _, _, w, _ in rows}
    assert periods == {"Q1": 12, "Q2": 12, "Q3": 12, "Q4": 16, "FY": 52}


def test_derive_calendar_rejects_gaps():
    cf = _cf(
        [
            _ctx("2024-01-29", "2024-04-28"),
            _ctx("2024-05-06", "2024-08-04"),  # a week is missing before this
            {"start": "2024-01-29", "end": "2025-01-26", "val": 1, "accn": "fy", "form": "10-K"},
        ]
    )
    with pytest.raises(FactsLoadError):
        derive_calendar(iter_entries(cf), NVDA_FY25, week_based=True)


def test_upsert_calendar_never_overwrites_a_disagreeing_row(conn, company_id):
    nvda = company_id("NVDA")
    # seeded NVDA Q1 FY2025 is 2024-01-29 → 2024-04-28; feed a contradiction
    with pytest.raises(FactsLoadError):
        upsert_calendar(
            conn, nvda, 2025,
            [("Q1", date(2024, 2, 5), date(2024, 5, 5), 13, "BAD")],
            {},
        )


# ---------- supersession pass (U11; gate check 9) ----------


def test_supersession_links_only_value_changes(conn, company_id):
    jnj = company_id("JNJ")
    filings = [
        _filing("S-ORIG", "10-K", "2024-02-10T16:00:00"),
        _filing("S-SAME", "10-Q", "2024-05-01T16:00:00"),
        _filing("S-RECAST", "10-K", "2025-02-20T16:00:00"),
    ]
    for filing in filings:
        _register(conn, jnj, filing)
    cf = _cf(
        [
            {"start": "2023-01-02", "end": "2023-12-31", "val": 100, "accn": "S-ORIG", "form": "10-K"},
            {"start": "2023-01-02", "end": "2023-12-31", "val": 100, "accn": "S-SAME", "form": "10-Q"},
            {"start": "2023-01-02", "end": "2023-12-31", "val": 90, "accn": "S-RECAST", "form": "10-K"},
        ]
    )
    corpus = {f.accession: f.acceptance for f in filings}
    rows, _, _ = select_rows(iter_entries(cf), corpus, {})
    insert_rows(conn, jnj, rows)
    links = supersession_pass(conn, jnj)
    # both same-value rows get superseded by the recast; not by each other
    old_new = {
        conn.execute("SELECT accession FROM facts WHERE fact_id = %s", (old,)).fetchone()[0]:
        conn.execute("SELECT accession FROM facts WHERE fact_id = %s", (new,)).fetchone()[0]
        for old, new in links
    }
    assert old_new == {"S-ORIG": "S-RECAST", "S-SAME": "S-RECAST"}
    # as-of BEFORE the recast: the original 100 is authoritative
    from us_rag.store.asof import AsOfContext

    before = AsOfContext(conn, _dt("2024-12-31T00:00:00")).facts(
        company_id=jnj, concept="Revenues", period_end=date(2023, 12, 31)
    )
    assert {r["value"] for r in before} == {100}
    after = AsOfContext(conn, _dt("2025-12-31T00:00:00")).facts(
        company_id=jnj, concept="Revenues", period_end=date(2023, 12, 31)
    )
    assert {r["value"] for r in after} == {90}


def test_supersession_pass_is_idempotent(conn, company_id):
    jnj = company_id("JNJ")
    filings = [
        _filing("I-ORIG", "10-K", "2024-02-10T16:00:00"),
        _filing("I-RECAST", "10-K", "2025-02-20T16:00:00"),
    ]
    for filing in filings:
        _register(conn, jnj, filing)
    cf = _cf(
        [
            {"start": "2022-01-03", "end": "2023-01-01", "val": 5, "accn": "I-ORIG", "form": "10-K"},
            {"start": "2022-01-03", "end": "2023-01-01", "val": 6, "accn": "I-RECAST", "form": "10-K"},
        ]
    )
    corpus = {f.accession: f.acceptance for f in filings}
    rows, _, _ = select_rows(iter_entries(cf), corpus, {})
    insert_rows(conn, jnj, rows)
    assert len(supersession_pass(conn, jnj)) == 1
    assert supersession_pass(conn, jnj) == []  # second run: nothing left to link
