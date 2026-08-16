"""Phase 3 exercise — Reciprocal Rank Fusion.

Implement rrf(): given several ranked lists of item ids (best first), score each item as
the SUM over lists of 1 / (k + rank), where rank is 1-based, and return the items ordered
best-first. Break ties by smaller id (so the result is deterministic).

Run:  uv run python learn/exercises/phase03_rrf_exercise.py
Goal: every check prints PASS. Peek at src/us_rag/query/retrieve.py (rrf_fuse) when stuck.
"""


def rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    # TODO: your turn.
    raise NotImplementedError


# ---- self-checks (do not edit) ----
def _check():
    dense = [10, 20, 30]   # ranks: 10->1, 20->2, 30->3
    sparse = [20, 40, 10]  # ranks: 20->1, 40->2, 10->3

    order = rrf([dense, sparse])
    # 20 = 1/62 + 1/61 (agreement) beats 10 = 1/61 + 1/63
    assert order[0] == 20, f"agreement should win; got {order}"
    assert set(order) == {10, 20, 30, 40}, f"all items present; got {order}"

    # deterministic tie-break: both appear once at rank 1 -> lower id first
    assert rrf([[7], [5]]) == [5, 7], "ties break by smaller id"

    # a single list just returns its own order
    assert rrf([[3, 1, 2]]) == [3, 1, 2], "single list preserved"
    print("PASS — you fused two rankings the way the retriever does")


if __name__ == "__main__":
    _check()
