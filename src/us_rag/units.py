"""Unit normalizer (design §4.6) — fail-closed, Decimal-exact.

Roles:
1. Parse quantities out of narrative text ("$1,240 million", "(1,234)" under a
   "$ in millions" header, "350 bps") into exact Decimals.
2. Validate XBRL-sourced values: normalize_xbrl() is an identity mapping — the
   invariant is that structured values pass through EXACTLY (no float round-trip).

Hard rules:
- A scalable quantity with no scale (inline or header) is an ERROR, never a guess.
- Scale-exempt classes (per-share, ratios) reject scale words outright.
- Inline scale beats header scale (explicit beats ambient).
- All arithmetic in Decimal; floats never touch a value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal


class UnitError(ValueError):
    """Fail-closed: raised whenever a quantity cannot be normalized unambiguously."""


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    kind: str  # 'usd' | 'usd_per_share' | 'ratio' | 'shares'


SCALES = {
    "thousand": Decimal(10) ** 3,
    "k": Decimal(10) ** 3,
    "million": Decimal(10) ** 6,
    "m": Decimal(10) ** 6,
    "mm": Decimal(10) ** 6,
    "billion": Decimal(10) ** 9,
    "b": Decimal(10) ** 9,
    "bn": Decimal(10) ** 9,
    "trillion": Decimal(10) ** 12,
}
# 'M'/'B'/'K' only count as scales when uppercase ("15M"); the word forms are
# case-insensitive. 'mm'/'bn' are finance-conventional and lowercase.
CASE_SENSITIVE_SCALES = {"k": "K", "m": "M", "b": "B"}

SCALE_EXEMPT_CLASSES = {"per_share", "ratio"}

_QTY_RE = re.compile(
    r"""
    (?P<open>\()?\s*
    (?P<neg>-)?\s*
    (?P<cur>\$)?\s*
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*
    (?P<suffix>%|(?:bps|thousand|million|billion|trillion|mm|bn|[KMBkmb])\b)?
    \s*(?P<close>\))?
    """,
    re.VERBOSE | re.IGNORECASE,  # word scales any case; single-letter K/M/B stay case-checked
)


def _scale_from_token(token: str) -> Decimal | None:
    lower = token.lower()
    if lower in CASE_SENSITIVE_SCALES and len(token) == 1:
        # single letters are scales only in their conventional uppercase form
        return SCALES[lower] if token == CASE_SENSITIVE_SCALES[lower] else None
    return SCALES.get(lower)


def header_scale(header_text: str) -> Decimal:
    """Extract the declared statement scale from a table header ("$ in millions")."""
    match = re.search(r"in\s+(thousands|millions|billions)", header_text, re.IGNORECASE)
    if not match:
        raise UnitError(f"no scale declaration found in header: {header_text!r}")
    return SCALES[match.group(1).lower().rstrip("s")]


def parse_quantity(
    text: str,
    *,
    header: Decimal | None = None,
    metric_class: str = "currency",
) -> Quantity:
    """Find and normalize the first quantity in `text`. Fail-closed on ambiguity."""
    match = _QTY_RE.search(text)
    if not match or not match.group("num"):
        raise UnitError(f"no quantity found in {text!r}")

    value = Decimal(match.group("num").replace(",", ""))
    negative = bool(match.group("neg"))
    if match.group("open") and match.group("close"):
        negative = True  # accounting negatives: (1,234)
    elif match.group("open") or match.group("close"):
        raise UnitError(f"unbalanced parentheses around quantity in {text!r}")

    suffix = match.group("suffix")

    # ratios: % / bps — never scaled, currency symbol nonsensical
    if suffix in ("%", "bps"):
        if metric_class not in ("ratio", "currency"):
            raise UnitError(f"{suffix} quantity not valid for metric class {metric_class!r}")
        divisor = Decimal(100) if suffix == "%" else Decimal(10000)
        result = value / divisor
        return Quantity(-result if negative else result, "ratio")

    if metric_class == "ratio":
        raise UnitError(f"ratio metric requires %% or bps in {text!r}")

    scale = _scale_from_token(suffix) if suffix else None
    if suffix and scale is None:
        raise UnitError(f"unrecognized scale token {suffix!r} in {text!r}")

    if metric_class in SCALE_EXEMPT_CLASSES:
        if scale is not None:
            raise UnitError(
                f"metric class {metric_class!r} is scale-exempt but {text!r} carries a scale"
            )
        kind = "usd_per_share" if metric_class == "per_share" else "ratio"
        return Quantity(-value if negative else value, kind)

    # scalable classes: currency, shares — a scale MUST come from somewhere
    effective = scale if scale is not None else header  # inline beats header
    if effective is None:
        raise UnitError(
            f"bare quantity with no scale context in {text!r} — refusing to guess (design §4.6)"
        )
    result = value * effective
    kind = "shares" if metric_class == "shares" else "usd"
    return Quantity(-result if negative else result, kind)


def render(q: Quantity) -> str:
    """Canonical rendering; parse_quantity(render(q)) == q (property-tested)."""
    if q.kind == "usd":
        millions = q.value / SCALES["million"]
        sign = "-" if millions < 0 else ""
        return f"{sign}${format(abs(millions).normalize(), ',f')} million"
    if q.kind == "usd_per_share":
        sign = "-" if q.value < 0 else ""
        return f"{sign}${format(abs(q.value).normalize(), ',f')}"
    if q.kind == "ratio":
        pct = (q.value * 100).normalize()
        return f"{format(pct, ',f')}%"
    if q.kind == "shares":
        millions = q.value / SCALES["million"]
        return f"{format(millions.normalize(), ',f')} million"
    raise UnitError(f"unknown kind {q.kind!r}")


def normalize_xbrl(value: int | str | Decimal, unit: str) -> Quantity:
    """XBRL facts arrive exact — this is a typed identity, never a transformation.

    The invariant (gate-tested): Decimal in == Decimal out, bit-for-bit. Floats are
    rejected because a float has already destroyed exactness upstream.
    """
    if isinstance(value, float):
        raise UnitError("float rejected: XBRL values must arrive as int/str/Decimal")
    kinds = {"USD": "usd", "USD/shares": "usd_per_share", "shares": "shares", "pure": "ratio"}
    if unit not in kinds:
        raise UnitError(f"unmapped XBRL unit {unit!r}")
    return Quantity(Decimal(str(value)), kinds[unit])
