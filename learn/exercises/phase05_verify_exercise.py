"""Phase 5 exercise — the verifier's core.

Implement verify(): decide whether an answer's claimed number may be emitted.
Rules:
  * if the source ABSTAINED (source_value is None), a claimed number is a violation;
    claiming nothing (claimed is None) is fine.
  * otherwise the claim passes if it equals the source exactly, OR is the source rounded
    to the claim's own number of decimal places (narrated rounding — "0.47" for 0.4690…).
Return (ok: bool, reason: str).

Run:  uv run python learn/exercises/phase05_verify_exercise.py
Goal: every check prints PASS. Peek at src/us_rag/query/verify.py when stuck.
"""

from decimal import Decimal


def verify(claimed, source_value) -> tuple[bool, str]:
    """claimed / source_value are Decimal or None (None on source = abstained)."""
    # TODO: your turn.
    raise NotImplementedError


# ---- self-checks (do not edit) ----
def _check():
    D = Decimal
    assert verify(D("416161000000"), D("416161000000"))[0], "exact match passes"
    assert not verify(D("416161000001"), D("416161000000"))[0], "off-by-one fails"
    assert verify(D("0.47"), D("0.4690516"))[0], "narrated rounding to 2 dp passes"
    assert verify(D("0.469"), D("0.4690516"))[0], "rounding to 3 dp passes"
    assert not verify(D("0.42"), D("0.4690516"))[0], "wrong rounding fails"

    ok, reason = verify(D("0.55"), None)
    assert not ok and "abstain" in reason.lower(), "a number on an abstained metric is a violation"
    assert verify(None, None)[0], "abstaining with no number is correct"
    print("PASS — you built the safety net that stops a confident wrong number")


if __name__ == "__main__":
    _check()
