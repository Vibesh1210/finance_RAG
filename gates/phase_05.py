"""Phase 5 gate = the M0 gate (execution plan Phase 5): the full answer contract.

Fixtures-only and model-free: numbers come from the deterministic executor, refusals and
clarifications are templated, and the look-ahead check drives the retrieval legs with a
dummy vector (the as-of filter is vector-independent). The LLM narrative path is opt-in
and is NOT exercised here (it would be an external call) — its retrieval half is already
gated by phase_03.

M0 exit criteria: quant exact-match ≥ 90% (answerable); 100% typed abstention on
unanswerables; zero look-ahead; every emitted number cited; router misroute baseline
recorded; JPM / non-comparable / clarify behaviours verified.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from common import ROOT, run_gate

from us_rag.db import connect_ro
from us_rag.eval.golden import load_bank
from us_rag.eval.lookahead import scan
from us_rag.query.generate import answer
from us_rag.query.router import classify, scan_entities

FACTUAL = load_bank(ROOT / "golden" / "factual_v0.yaml", "factual")
QUANT = load_bank(ROOT / "golden" / "quant_v0.yaml", "quant")
_DUMMY = [0.03125] * 1024  # model-free embedder for the look-ahead legs


def _expected_route(q) -> str:
    if q.expected == "abstain":
        return "unanswerable"
    if q.expected == "typed_refusal":
        return "graph"
    if q.expected == "clarify":
        return "clarify"
    if q.kind == "quant":
        return "metric"
    if q.category == "cross_company":
        return "narrative" if any(w in q.question.lower() for w in ("describe", "how do", "how does")) else "metric"
    return "narrative"


def check_quant_exact_match() -> None:
    answerable = [q for q in QUANT if q.expected == "answer"]
    hits, misses = 0, []
    with connect_ro() as ro:
        for q in answerable:
            a = answer(ro, q.question, as_of=date(2026, 3, 1))
            got = a.numbers[0].value if (a.status == "answered" and a.numbers) else None
            if got is not None and Decimal(str(got)) == Decimal(str(q.gold_value)):
                hits += 1
            else:
                misses.append(f"{q.id} (got {got} want {q.gold_value}, status {a.status})")
    rate = hits / len(answerable)
    if rate < 0.90:
        raise AssertionError(f"quant exact-match {rate:.0%} < 90% — misses: {'; '.join(misses)}")


def check_every_number_cited() -> None:
    with connect_ro() as ro:
        for q in [q for q in QUANT if q.expected == "answer"]:
            a = answer(ro, q.question, as_of=date(2026, 3, 1))
            if a.status == "answered" and not a.citations:
                raise AssertionError(f"{q.id}: emitted a number with no citation")


def check_typed_abstention() -> None:
    unanswerable = [q for q in FACTUAL if q.expected in ("abstain", "typed_refusal")]
    bad = []
    with connect_ro() as ro:
        for q in unanswerable:
            a = answer(ro, q.question, as_of=date(2026, 3, 1))
            if a.status != "refused":
                bad.append(f"{q.id} ({a.status})")
    if bad:
        raise AssertionError(f"{len(bad)}/{len(unanswerable)} unanswerables not refused: {'; '.join(bad)}")


def check_clarify() -> None:
    clarifies = [q for q in FACTUAL + QUANT if q.expected == "clarify"]
    bad = []
    with connect_ro() as ro:
        for q in clarifies:
            if answer(ro, q.question, as_of=date(2026, 3, 1)).status != "clarify":
                bad.append(q.id)
    if bad:
        raise AssertionError(f"clarify questions not clarified: {bad}")


def check_no_look_ahead() -> None:
    with connect_ro() as ro:
        leaks, meaningful = scan(ro, FACTUAL + QUANT, lambda _q: _DUMMY)
    if leaks:
        raise AssertionError(f"{len(leaks)} look-ahead leak(s): {leaks[:3]}")
    if meaningful < 3:
        raise AssertionError(f"look-ahead near-vacuous ({meaningful} historical samples)")


def check_jpm_behaviors() -> None:
    with connect_ro() as ro:
        rev = answer(ro, "What was JPMorgan Chase's total net revenue for fiscal year 2025?", as_of=date(2026, 3, 1))
        gm = answer(ro, "Compare JPMorgan's gross margin to Apple's for fiscal 2025.", as_of=date(2026, 3, 1))
    if rev.status != "answered" or not rev.reason:  # reason carries the comparability caveat
        raise AssertionError(f"JPM revenue should answer with a caveat, got {rev.status}/{rev.reason}")
    if gm.status == "answered":
        raise AssertionError("JPM gross margin must not be answered with a number")


def check_router_baseline() -> None:
    bank = FACTUAL + QUANT
    with connect_ro() as ro:
        ok = sum(1 for q in bank if classify(q.question, scan_entities(ro, q.question)).route == _expected_route(q))
    rate = ok / len(bank)
    print(f"      router accuracy: {ok}/{len(bank)} = {rate:.0%} (M0 baseline)")
    if rate < 0.85:
        raise AssertionError(f"router accuracy {rate:.0%} < 0.85 baseline floor")


run_gate(
    "phase_05",
    [
        ("quant exact-match >= 90% on answerable quant", check_quant_exact_match),
        ("every emitted number is cited", check_every_number_cited),
        ("100% typed abstention on unanswerables", check_typed_abstention),
        ("ambiguous questions are clarified, not answered", check_clarify),
        ("zero look-ahead across the golden as-of samples", check_no_look_ahead),
        ("JPM: revenue caveated; gross margin not numerically answered", check_jpm_behaviors),
        ("router misroute baseline recorded (>= 0.85)", check_router_baseline),
    ],
)
