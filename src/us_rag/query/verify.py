"""Verifier v1 (design §6.4): the hard post-check that guards every number the SQL path
emits.

A claimed number passes ONLY if it exactly matches — to full precision, with a tolerance
for narrated rounding — the value the deterministic executor produced for the same
(entity, metric, period, as-of); its citation is the authoritative accession for that
as-of; a non-comparable metric is not claimed as comparable; and any *derived* number
carries a computation record (the no-LLM-arithmetic rule). A number the executor abstains
on may not be emitted at all.

In Phase 5 this runs after generation (mismatch → one regenerate → abstain). Here it is
the standalone primitive with unit-tested match logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from us_rag.query.metrics import (
    Abstention,
    DerivedResult,
    MetricResult,
    Q4Result,
    SegmentResult,
)

_WITH_VALUE = (MetricResult, DerivedResult, Q4Result, SegmentResult)


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str


def rounds_to(exact: Decimal, claim: Decimal) -> bool:
    """True if `claim` equals `exact` rounded to the claim's own number of decimal places.
    Narrated forms (e.g. '0.47' for 0.4690…) are allowed; the citation still carries full
    precision, and the verifier compares against that."""
    exponent = claim.as_tuple().exponent
    places = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    quantum = Decimal(1).scaleb(-places)
    return exact.quantize(quantum) == claim


def _matches(exact: Decimal, claimed) -> bool:
    try:
        claim = Decimal(str(claimed))
    except (InvalidOperation, ValueError):
        return False
    return exact == claim or rounds_to(exact, claim)


def _is_comparable(result) -> bool:
    # MetricResult carries an explicit flag; derived/segment signal non-comparability
    # by attaching a caveat (they inherit it from a non-comparable input).
    if isinstance(result, MetricResult):
        return result.comparable
    return getattr(result, "caveat", None) is None


def verify(
    result,
    *,
    claimed_value=None,
    claimed_accession: str | None = None,
    claimed_comparable: bool | None = None,
) -> Verdict:
    """Check an executor result against what an answer claims about it."""
    if isinstance(result, Abstention):
        if claimed_value is not None:
            return Verdict(False, f"emitted a number for an abstaining metric ({result.reason})")
        return Verdict(True, f"correctly abstains ({result.reason})")

    if not isinstance(result, _WITH_VALUE):
        return Verdict(False, f"unverifiable result type {type(result).__name__}")

    # no-LLM-arithmetic: a derived number must carry a computation record
    if isinstance(result, DerivedResult) and not result.computation:
        return Verdict(False, "derived number lacks a computation record")
    if isinstance(result, Q4Result) and result.derived and not result.computation:
        return Verdict(False, "derived Q4 lacks a computation record")

    # numeric exact-match (with narrated-rounding tolerance)
    if claimed_value is not None and not _matches(result.value, claimed_value):
        return Verdict(False, f"claimed {claimed_value} != source {result.value}")

    # citation precedence (§4.2): the cited accession must be the authoritative one
    citation = getattr(result, "citation", None)
    if claimed_accession is not None and citation is not None and claimed_accession != citation.accession:
        return Verdict(False, f"cited {claimed_accession} != authoritative {citation.accession}")

    # comparability enforcement: don't let an answer claim comparability the source denies
    if claimed_comparable is True and not _is_comparable(result):
        return Verdict(False, "claimed comparable, but the metric is flagged not comparable")

    return Verdict(True, "verified")
