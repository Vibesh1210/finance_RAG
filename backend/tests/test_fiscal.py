"""Fiscal resolver trap matrix (execution plan Phase 1) — every row a test.

The seeds behind these tests are hand-entered from filings and cross-checked
against XBRL contexts at Phase 2; here we test the RESOLVER's behavior."""

from datetime import date

import pytest

from us_rag.fiscal import FiscalGapError, resolve


def r(conn, company_id, ticker, text):
    return resolve(conn, company_id(ticker), ticker, text)


def test_nvda_q3_fy2025_is_october(conn, company_id):
    res = r(conn, company_id, "NVDA", "Q3 FY2025")
    assert res.period_end == date(2024, 10, 27)  # NOT calendar Q3 2025
    assert not res.ambiguous


def test_msft_q1_fy2025(conn, company_id):
    res = r(conn, company_id, "MSFT", "Q1 FY2025")
    assert (res.period_start, res.period_end) == (date(2024, 7, 1), date(2024, 9, 30))


def test_aapl_fy2024_ends_september(conn, company_id):
    assert r(conn, company_id, "AAPL", "FY2024").period_end == date(2024, 9, 28)


def test_wmt_vs_nvda_fy2025_same_month_different_dates(conn, company_id):
    wmt = r(conn, company_id, "WMT", "FY2025")
    nvda = r(conn, company_id, "NVDA", "FY2025")
    assert wmt.period_end != nvda.period_end
    assert (wmt.period_end.year, wmt.period_end.month) == (2025, 1)
    assert (nvda.period_end.year, nvda.period_end.month) == (2025, 1)


def test_cat_q3_2024_fiscal_equals_calendar(conn, company_id):
    res = r(conn, company_id, "CAT", "Q3 2024")
    assert (res.period_start, res.period_end) == (date(2024, 7, 1), date(2024, 9, 30))
    assert res.fiscal_equals_calendar and not res.ambiguous


def test_de_q3_2024_is_fiscal_with_note(conn, company_id):
    res = r(conn, company_id, "DE", "Q3 2024")
    assert (res.period_start, res.period_end) == (date(2024, 4, 29), date(2024, 7, 28))
    assert res.ambiguous and "fiscal" in res.interpretation


def test_nvda_bare_year_maps_to_fy2025(conn, company_id):
    res = r(conn, company_id, "NVDA", "revenue in 2024")
    assert res.fiscal_year == 2025 and res.ambiguous
    assert "FY2025" in res.interpretation and "2024" in res.interpretation


def test_wmt_bare_year_vs_fy_label_differ(conn, company_id):
    bare = r(conn, company_id, "WMT", "2024")
    labeled = r(conn, company_id, "WMT", "FY2024")
    assert bare.fiscal_year == 2025 and labeled.fiscal_year == 2024
    assert bare.period_end != labeled.period_end
    assert str(bare.period_start) in bare.interpretation
    assert str(labeled.period_start) in labeled.interpretation


def test_missing_period_errors_never_formula(conn, company_id):
    with pytest.raises(FiscalGapError, match="U8"):
        r(conn, company_id, "NVDA", "Q2 FY2023")


def test_no_period_expression_errors(conn, company_id):
    with pytest.raises(FiscalGapError, match="no fiscal-period expression"):
        r(conn, company_id, "NVDA", "how is business")


def test_de_fy2025_seeded_as_53_weeks(conn, company_id):
    row = conn.execute(
        "SELECT weeks FROM fiscal_calendars WHERE company_id = %s AND fiscal_year = 2025"
        " AND fiscal_period = 'FY'",
        (company_id("DE"),),
    ).fetchone()
    assert row == (53,)


def test_bare_year_without_rows_is_gap_not_formula(conn, company_id):
    with pytest.raises(FiscalGapError, match="U8"):
        r(conn, company_id, "AAPL", "2030")
