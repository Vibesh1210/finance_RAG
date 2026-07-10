"""Unit-normalizer fixture matrix (execution plan Phase 1) + round-trip property."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from us_rag.units import Quantity, UnitError, header_scale, normalize_xbrl, parse_quantity

MILLION = Decimal(10) ** 6


# --- the pinned fixture matrix: every row an exact assertion ---


def test_inline_million():
    assert parse_quantity("$1,240 million") == Quantity(Decimal(1_240_000_000), "usd")


def test_inline_billion():
    assert parse_quantity("$1.24 billion") == Quantity(Decimal(1_240_000_000), "usd")


def test_parens_negative_under_millions_header():
    q = parse_quantity("(1,234)", header=header_scale("$ in millions"))
    assert q == Quantity(Decimal(-1_234_000_000), "usd")


def test_thousands_header():
    q = parse_quantity("1,234", header=header_scale("(in thousands)"))
    assert q == Quantity(Decimal(1_234_000), "usd")


def test_eps_scale_exempt():
    q = parse_quantity("$6.13", metric_class="per_share")
    assert q == Quantity(Decimal("6.13"), "usd_per_share")


def test_percent_never_scaled():
    q = parse_quantity("revenue grew 122%", header=header_scale("in millions"))
    assert q == Quantity(Decimal("1.22"), "ratio")


def test_bps():
    assert parse_quantity("350 bps") == Quantity(Decimal("0.035"), "ratio")


def test_bare_number_rejected():
    with pytest.raises(UnitError, match="refusing to guess"):
        parse_quantity("1,240")


# --- fail-closed edges ---


def test_eps_with_scale_rejected():
    with pytest.raises(UnitError, match="scale-exempt"):
        parse_quantity("EPS of $6.13 million", metric_class="per_share")


def test_inline_beats_header():
    q = parse_quantity("$1.2 billion", header=header_scale("in millions"))
    assert q == Quantity(Decimal(1_200_000_000), "usd")


def test_negative_percent_parens():
    assert parse_quantity("(2.3%)") == Quantity(Decimal("-0.023"), "ratio")


def test_uppercase_M_is_million_lowercase_is_not():
    assert parse_quantity("$15M") == Quantity(Decimal(15_000_000), "usd")
    with pytest.raises(UnitError):
        parse_quantity("$15m")


def test_month_word_is_not_a_scale():
    with pytest.raises(UnitError, match="refusing to guess"):
        parse_quantity("$5 Months of revenue")


def test_header_without_scale_rejected():
    with pytest.raises(UnitError, match="no scale declaration"):
        header_scale("Consolidated Statements of Income")


def test_unbalanced_parens_rejected():
    with pytest.raises(UnitError, match="unbalanced"):
        parse_quantity("(1,234 million", header=header_scale("in millions"))


# --- XBRL passthrough invariant: exactness, no floats ---


def test_xbrl_identity_large_int():
    big = 391_035_000_000
    assert normalize_xbrl(big, "USD").value == Decimal(big)


def test_xbrl_identity_beyond_float_precision():
    v = 2**63 + 1  # a float would silently corrupt this
    assert normalize_xbrl(str(v), "USD").value == Decimal(v)


def test_xbrl_per_share_and_pure():
    assert normalize_xbrl("6.13", "USD/shares") == Quantity(Decimal("6.13"), "usd_per_share")
    assert normalize_xbrl("0.246", "pure") == Quantity(Decimal("0.246"), "ratio")


def test_xbrl_rejects_float():
    with pytest.raises(UnitError, match="float rejected"):
        normalize_xbrl(6.13, "USD")


def test_xbrl_rejects_unknown_unit():
    with pytest.raises(UnitError, match="unmapped"):
        normalize_xbrl(1, "EUR")


# --- property: normalize(render(q)) == q ---


from us_rag.units import render  # noqa: E402


@given(
    thousands=st.integers(min_value=1, max_value=10**10),
    sign=st.sampled_from([1, -1]),
)
def test_usd_round_trip(thousands: int, sign: int):
    q = Quantity(Decimal(sign * thousands * 1000), "usd")
    assert parse_quantity(render(q)) == q


@given(cents=st.integers(min_value=1, max_value=10**6))
def test_per_share_round_trip(cents: int):
    q = Quantity(Decimal(cents) / 100, "usd_per_share")
    assert parse_quantity(render(q), metric_class="per_share") == q


@given(bps=st.integers(min_value=-10**5, max_value=10**5).filter(lambda b: b != 0))
def test_ratio_round_trip(bps: int):
    q = Quantity(Decimal(bps) / 10_000, "ratio")
    assert parse_quantity(render(q)) == q
