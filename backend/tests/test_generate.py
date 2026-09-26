"""Answer-pipeline unit tests (pure: metric/period extraction, no DB/model)."""

from __future__ import annotations

from decimal import Decimal

from us_rag.query.generate import _as_reported, extract_metric_key, extract_period


def test_extract_metric_key():
    assert extract_metric_key("What was Apple's total net sales for FY2025?") == "revenue"
    assert extract_metric_key("Apple's net income") == "net_income"
    assert extract_metric_key("diluted earnings per share") == "diluted_eps"
    assert extract_metric_key("total assets") == "total_assets"
    assert extract_metric_key("What did the CEO say?") is None


def test_extract_period_year_forms():
    assert extract_period("for fiscal year 2025") == "FY2025"
    assert extract_period("for fiscal 2024") == "FY2024"
    assert extract_period("revenue FY2025") == "FY2025"
    assert extract_period("for the fiscal year ended January 26, 2025") == "FY2025"


def test_extract_period_quarter_forms():
    assert extract_period("revenue for Q3 FY2025") == "Q3 FY2025"
    assert extract_period("its fourth-quarter 2024 revenue") == "Q4 FY2024"


def test_extract_period_none_when_absent():
    assert extract_period("What was Walmart's revenue?") is None


def test_as_reported_scale_and_per_share():
    assert _as_reported(Decimal("416161000000"), "USD") == "$416,161 million"
    assert _as_reported(Decimal("13.64"), "USD/shares") == "$13.64 per share"
