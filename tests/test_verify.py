"""Verifier v1 unit tests (pure: constructed executor results, no DB/model)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from us_rag.query.metrics import Abstention, Citation, DerivedResult, MetricResult
from us_rag.query.verify import rounds_to, verify

CITE = Citation("0000320193-25-000079", "FY2025", date(2026, 3, 1))


def _mr(value, comparable=True):
    return MetricResult("revenue", "AAPL", Decimal(value), "USD", comparable,
                        date(2025, 9, 27), CITE, None if comparable else "bank caveat")


# ---- rounding tolerance ----


def test_rounds_to_accepts_narrated_form():
    assert rounds_to(Decimal("0.4690516"), Decimal("0.47")) is True
    assert rounds_to(Decimal("0.4690516"), Decimal("0.469")) is True


def test_rounds_to_rejects_wrong_rounding():
    assert rounds_to(Decimal("0.4690516"), Decimal("0.48")) is False


# ---- numeric match + citation ----


def test_exact_value_verifies():
    assert verify(_mr("416161000000"), claimed_value="416161000000").ok


def test_wrong_value_fails():
    v = verify(_mr("416161000000"), claimed_value="416161000001")
    assert not v.ok and "!= source" in v.reason


def test_wrong_citation_fails():
    v = verify(_mr("416161000000"), claimed_value="416161000000", claimed_accession="WRONG-ACCN")
    assert not v.ok and "authoritative" in v.reason


# ---- abstention guard ----


def test_number_on_abstention_is_a_violation():
    ab = Abstention("gross_margin", "JPM", "no_comparable_mapping", "banks have no gross profit")
    assert not verify(ab, claimed_value="0.55").ok
    assert verify(ab, claimed_value=None).ok  # abstaining with no number is correct


# ---- comparability + derived record ----


def test_claiming_comparable_on_noncomparable_fails():
    v = verify(_mr("182447000000", comparable=False), claimed_value="182447000000", claimed_comparable=True)
    assert not v.ok and "comparable" in v.reason


def test_derived_without_computation_record_fails():
    bad = DerivedResult("YoY", "NVDA", "revenue YoY", Decimal("1.14"), "ratio", "", [], None)
    assert not verify(bad, claimed_value="1.14").ok
