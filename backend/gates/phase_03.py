"""Phase 3 gate: eval harness, golden bank, hybrid retrieval, look-ahead (execution plan).

The look-ahead check (check 3) is the cardinal one — it gates every deploy (design §9).
It runs REAL retrieval, so it needs bge-m3 locally (the 'embed' group); this is local
compute, not an external data-API call, so it stays within the fixtures-only CI rule.

Status: the recall-baseline check (5) fails until the golden bank is [HUMAN]-verified and
`golden/thresholds.yaml` is frozen (ADR-0012) — expected, mirrors phase_02.
"""

from __future__ import annotations

from collections import Counter

from common import ROOT, run_gate

from us_rag.db import connect
from us_rag.eval.golden import load_bank
from us_rag.eval.harness import (
    check_ratchet,
    dense_retriever,
    fused_retriever,
    load_thresholds,
    run_factual,
    sparse_retriever,
)
from us_rag.eval.lookahead import scan

FACTUAL = ROOT / "golden" / "factual_v0.yaml"
QUANT = ROOT / "golden" / "quant_v0.yaml"
THRESHOLDS = ROOT / "golden" / "thresholds.yaml"

FACTUAL_DIST = {
    "point_in_time": 8, "segment": 8, "cross_company": 6, "narrative": 6,
    "graph": 4, "unanswerable": 6, "fiscal_trap": 2,
}
QUANT_DIST = {"direct_metric": 12, "fiscal_trap": 8}


def check_bank_valid() -> None:
    fac = load_bank(FACTUAL, "factual")  # raises on any schema error
    qnt = load_bank(QUANT, "quant")
    if len(fac) != 40 or len(qnt) != 20:
        raise AssertionError(f"bank sizes: factual {len(fac)} (want 40), quant {len(qnt)} (want 20)")
    fc, qc = dict(Counter(q.category for q in fac)), dict(Counter(q.category for q in qnt))
    if fc != FACTUAL_DIST:
        raise AssertionError(f"factual distribution {fc} != {FACTUAL_DIST}")
    if qc != QUANT_DIST:
        raise AssertionError(f"quant distribution {qc} != {QUANT_DIST}")


def check_leakage_lint() -> None:
    """A question must not give away its own answer (the accession or the gold number)."""
    bad = []
    for q in load_bank(QUANT, "quant"):
        if q.gold_value and q.gold_value.replace(".", "") in q.question.replace(",", ""):
            bad.append(f"{q.id}: gold_value leaks into question text")
    for q in load_bank(FACTUAL, "factual"):
        for p in q.gold:
            if p.accession in q.question:
                bad.append(f"{q.id}: gold accession leaks into question text")
    if bad:
        raise AssertionError("leakage: " + "; ".join(bad))


def check_look_ahead() -> None:
    """No retrieved chunk may be newer than the query's as_of — across the whole bank."""
    from us_rag.query.retrieve import embed_query

    questions = load_bank(FACTUAL, "factual") + load_bank(QUANT, "quant")
    with connect() as conn:
        leaks, meaningful = scan(conn, questions, embed_query)
    if leaks:
        sample = "; ".join(
            f"{leak.qid}/{leak.leg} chunk {leak.chunk_id} kt={leak.knowledge_time} > as_of {leak.as_of}"
            for leak in leaks[:5]
        )
        raise AssertionError(f"{len(leaks)} LOOK-AHEAD leak(s) [cardinal-rule bug]: {sample}")
    if meaningful < 3:  # plan floor: >=3 point-in-time questions in the 8-K->10-Q window
        raise AssertionError(
            f"look-ahead test near-vacuous: only {meaningful} questions have future chunks "
            "to exclude — the historical-as-of samples must stay in the bank"
        )


def check_rrf_beats_legs() -> None:
    """Sanity: fusing the two legs must not retrieve worse than either leg alone."""
    fac = load_bank(FACTUAL, "factual")
    with connect() as conn:
        fused = run_factual(fac, fused_retriever(conn))
        dense = run_factual(fac, dense_retriever(conn))
        sparse = run_factual(fac, sparse_retriever(conn))
    if not (fused.recall_at_10 >= dense.recall_at_10 and fused.recall_at_10 >= sparse.recall_at_10):
        raise AssertionError(
            f"fused recall@10 {fused.recall_at_10:.3f} does not beat dense "
            f"{dense.recall_at_10:.3f} / sparse {sparse.recall_at_10:.3f}"
        )


def check_recall_baseline() -> None:
    thresholds = load_thresholds(THRESHOLDS)
    if not thresholds:
        raise AssertionError(
            "[HUMAN] recall baseline not frozen — verify the 60-question golden bank, then "
            "record fused/dense/sparse baselines in golden/thresholds.yaml (ratchet-up only)"
        )
    fac = load_bank(FACTUAL, "factual")
    with connect() as conn:
        fused = run_factual(fac, fused_retriever(conn))
    fails = check_ratchet("fused", fused, thresholds)
    if fails:
        raise AssertionError("; ".join(fails))


run_gate(
    "phase_03",
    [
        ("1. golden bank schema-valid, committed, distribution correct", check_bank_valid),
        ("2. leakage lint: no question leaks its own answer", check_leakage_lint),
        ("3. LOOK-AHEAD: no retrieved chunk newer than as_of (cardinal rule)", check_look_ahead),
        ("4. hybrid (RRF) retrieval beats each single leg", check_rrf_beats_legs),
        ("5. recall@10 >= frozen baseline on factual_v0 [HUMAN: freeze after verify]", check_recall_baseline),
    ],
)
