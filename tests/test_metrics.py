"""Metric-registry resolver unit tests (pure: no DB, no model). The end-to-end
metric_value path is exercised by the Phase 4 gate against the live facts."""

from __future__ import annotations

from datetime import date

from us_rag.query.metrics import Mapping, pick_mapping


def _m(company_id, tag, valid_from=None, comparable=True):
    return Mapping("revenue", company_id, tag, "USD", comparable, None, valid_from)


def test_company_override_beats_default():
    chosen = pick_mapping([_m(None, "Revenues"), _m(5, "RevenueFromContract")], date(2025, 1, 1))
    assert chosen.company_id == 5 and chosen.us_gaap_tag == "RevenueFromContract"


def test_default_used_when_no_override():
    assert pick_mapping([_m(None, "Revenues")], date(2025, 1, 1)).us_gaap_tag == "Revenues"


def test_null_tag_row_is_a_chosen_abstention():
    # a company row with us_gaap_tag=None wins and signals "abstain" (e.g. JPM gross profit)
    chosen = pick_mapping([_m(None, "GrossProfit"), _m(7, None)], date(2025, 1, 1))
    assert chosen.company_id == 7 and chosen.us_gaap_tag is None


def test_valid_from_hides_not_yet_effective_mapping():
    rows = [_m(None, "OldTag"), _m(None, "NewTag", valid_from=date(2025, 1, 1))]
    assert pick_mapping(rows, date(2024, 6, 1)).us_gaap_tag == "OldTag"
    assert pick_mapping(rows, date(2025, 6, 1)).us_gaap_tag == "NewTag"


def test_none_when_nothing_applies():
    assert pick_mapping([], date(2025, 1, 1)) is None
    assert pick_mapping([_m(None, "X", valid_from=date(2030, 1, 1))], date(2025, 1, 1)) is None


# ---- derived-metric arithmetic (pure, Decimal, deterministic) ----

from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402

from us_rag.query.metrics import _cagr, _pct_change, _ratio  # noqa: E402


def test_pct_change_is_year_over_year_growth():
    # NVDA revenue FY2024 -> FY2025: 60,922M -> 130,497M ≈ +114.2%
    v = _pct_change(Decimal("130497"), Decimal("60922"))
    assert float(v) == pytest.approx(1.1421, abs=1e-4)


def test_ratio_is_exact():
    assert _ratio(Decimal("100"), Decimal("400")) == Decimal("0.25")


def test_cagr_geometric():
    # 100 -> 400 over 2 years = 100% CAGR (100 -> 200 -> 400)
    assert float(_cagr(Decimal("100"), Decimal("400"), 2)) == pytest.approx(1.0, abs=1e-9)
    # one-year CAGR equals simple growth
    assert float(_cagr(Decimal("100"), Decimal("150"), 1)) == pytest.approx(0.5, abs=1e-9)


# ---- Q4 derivation arithmetic & period-tiling guard (pure) ----

from us_rag.query.metrics import _q4_derive, periods_contiguous  # noqa: E402


def test_q4_is_full_year_minus_first_three_quarters():
    assert _q4_derive(Decimal("130497"), Decimal("26044"), Decimal("30040"), Decimal("35082")) == Decimal("39331")


def test_periods_contiguous_accepts_clean_tiling():
    q = [(date(2024, 1, 1), date(2024, 3, 31)), (date(2024, 4, 1), date(2024, 6, 30)),
         (date(2024, 7, 1), date(2024, 9, 30))]
    assert periods_contiguous(date(2024, 1, 1), date(2024, 12, 31), q) is True


def test_periods_contiguous_rejects_a_gap():
    q = [(date(2024, 1, 1), date(2024, 3, 31)), (date(2024, 4, 2), date(2024, 6, 30)),
         (date(2024, 7, 1), date(2024, 9, 30))]  # 1-day gap before Q2
    assert periods_contiguous(date(2024, 1, 1), date(2024, 12, 31), q) is False


def test_periods_contiguous_rejects_no_room_for_q4():
    q = [(date(2024, 1, 1), date(2024, 4, 30)), (date(2024, 5, 1), date(2024, 8, 31)),
         (date(2024, 9, 1), date(2024, 12, 31))]  # Q3 ends at year end -> no Q4
    assert periods_contiguous(date(2024, 1, 1), date(2024, 12, 31), q) is False
