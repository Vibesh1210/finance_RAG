"""Eval harness unit tests — metrics, golden loader, and the runner with a stub
retriever. All pure (no DB, no model) so they run in the fast suite."""

from __future__ import annotations

import math
from datetime import date

import pytest

from us_rag.eval.golden import GoldPassage, Question, load_bank
from us_rag.eval.harness import BankResult, check_ratchet, run_factual
from us_rag.eval.metrics import ndcg_at_k, recall_at_k, reciprocal_rank

A, B, C, D = ("acc1", "Item 1A"), ("acc1", "Item 7"), ("acc2", "Item 1A"), ("acc3", "Item 7")


# ---------- metrics ----------


def test_recall_at_k():
    assert recall_at_k([A, B, C], {A, C}, k=3) == 1.0
    assert recall_at_k([A, B, C], {A, C}, k=1) == 0.5
    assert recall_at_k([B, D], {A, C}, k=10) == 0.0
    assert recall_at_k([A], set(), k=10) is None  # undefined without gold


def test_reciprocal_rank():
    assert reciprocal_rank([B, A, C], {A}) == 0.5   # first gold at rank 2
    assert reciprocal_rank([A, B], {A}) == 1.0
    assert reciprocal_rank([B, C], {A}) == 0.0      # not retrieved


def test_ndcg_rewards_higher_rank():
    assert ndcg_at_k([A, B], {A}, k=2) == pytest.approx(1.0)              # gold at top -> ideal
    assert ndcg_at_k([B, A], {A}, k=2) == pytest.approx(1 / math.log2(3))  # gold at rank 2
    assert ndcg_at_k([A], set(), k=2) is None


# ---------- golden loader ----------


def test_load_bank_and_validate(tmp_path):
    p = tmp_path / "factual_v0.yaml"
    p.write_text(
        "- id: F001\n"
        "  question: What supply-chain risks did Apple flag?\n"
        "  category: narrative\n"
        "  as_of: 2025-06-01\n"
        "  company: AAPL\n"
        "  gold:\n"
        "    - {accession: '0000320193-24-000123', section: 'Item 1A'}\n"
    )
    bank = load_bank(p, "factual")
    assert len(bank) == 1
    q = bank[0]
    assert q.as_of == date(2025, 6, 1)
    assert q.gold_keys == {("0000320193-24-000123", "Item 1A")}
    assert q.expected == "retrieve"


def test_loader_rejects_unknown_category(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "- id: X\n  question: q\n  category: nonsense\n  as_of: 2025-01-01\n"
        "  gold: [{accession: a, section: s}]\n"
    )
    with pytest.raises(ValueError, match="unknown category"):
        load_bank(p, "factual")


def test_loader_rejects_retrieve_without_gold(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("- id: X\n  question: q\n  category: narrative\n  as_of: 2025-01-01\n")
    with pytest.raises(ValueError, match="no gold passages"):
        load_bank(p, "factual")


# ---------- runner with a stub retriever ----------


def _q(qid, gold, company=None):
    return Question(
        id=qid, question="q", kind="factual", category="narrative",
        as_of=date(2025, 1, 1), company=company,
        gold=[GoldPassage(*g) for g in gold],
    )


def test_run_factual_aggregates():
    questions = [_q("F1", [("a", "s")]), _q("F2", [("b", "s")])]
    # stub: F1 finds its gold at rank 1; F2 misses entirely
    rankings = {"F1": [("a", "s"), ("z", "s")], "F2": [("y", "s"), ("z", "s")]}
    result = run_factual(questions, lambda q: rankings[q.id])
    assert result.n == 2
    assert result.recall_at_10 == pytest.approx(0.5)   # 1.0 + 0.0, /2
    assert result.mrr == pytest.approx(0.5)             # 1.0 + 0.0, /2


def test_check_ratchet_flags_regression():
    r = BankResult(n=40, recall_at_10=0.70, mrr=0.55, ndcg_at_10=0.60)
    thresholds = {"fused": {"recall_at_10": 0.75, "mrr": 0.50, "ndcg_at_10": 0.55}}
    fails = check_ratchet("fused", r, thresholds)
    assert len(fails) == 1 and "recall_at_10" in fails[0]  # only recall dropped below baseline
    assert check_ratchet("fused", r, {}) == []             # no baseline yet -> nothing to fail
