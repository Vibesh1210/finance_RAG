"""Hybrid-retrieval unit tests. The fusion math is pure (no DB, no model) so it runs in
the fast suite; the as-of pushdown and end-to-end retrieval are exercised by the Phase 3
look-ahead gate against the live corpus (they need bge-m3 + embedded chunks)."""

from __future__ import annotations

import pytest

from us_rag.query.retrieve import RRF_K, rrf_fuse


def test_rrf_fusion_sums_reciprocal_ranks():
    dense = [10, 20, 30]   # ranks 10->1, 20->2, 30->3
    sparse = [20, 40, 10]  # ranks 20->1, 40->2, 10->3
    fused = dict(rrf_fuse([dense, sparse], top_k=10))
    assert fused[20] == pytest.approx(1 / (RRF_K + 2) + 1 / (RRF_K + 1))
    assert fused[10] == pytest.approx(1 / (RRF_K + 1) + 1 / (RRF_K + 3))
    assert fused[30] == pytest.approx(1 / (RRF_K + 3))
    assert fused[40] == pytest.approx(1 / (RRF_K + 2))


def test_rrf_agreement_beats_single_high_rank():
    # 20 is rank2+rank1 (both legs agree); 10 is rank1+rank3. Agreement wins.
    order = [cid for cid, _ in rrf_fuse([[10, 20, 30], [20, 40, 10]], top_k=10)]
    assert order[0] == 20


def test_rrf_ties_break_by_chunk_id():
    # both appear once at rank 1 -> equal score -> lower chunk_id first (deterministic)
    order = [cid for cid, _ in rrf_fuse([[7], [5]], top_k=10)]
    assert order == [5, 7]


def test_rrf_respects_top_k():
    fused = rrf_fuse([[1, 2, 3, 4, 5], [5, 4, 3, 2, 1]], top_k=2)
    assert len(fused) == 2


def test_rrf_empty_input():
    assert rrf_fuse([[], []], top_k=10) == []
