"""Phase 2 exercise — the heading-aware packer.

Implement pack(): greedily group paragraphs into chunks so each chunk stays within a
token budget (never exceeding it once it holds at least one paragraph). Approximate a
paragraph's token count as len(text) // 4 (the same rough budget the real chunker uses).

Run:  uv run python docs/learning_docs/exercises/phase02_chunk_exercise.py
Goal: every check prints PASS. Peek at src/us_rag/ingest/narrative.py only when stuck.
"""


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def pack(paragraphs: list[str], budget_tokens: int) -> list[list[str]]:
    """Return a list of chunks; each chunk is a list of paragraphs whose combined
    approx_tokens is <= budget_tokens (a single oversized paragraph gets its own chunk)."""
    # TODO: your turn. Greedy: keep adding to the current chunk until the next paragraph
    # would push it over budget, then start a new chunk.
    raise NotImplementedError


# ---- self-checks (do not edit) ----
def _check():
    a, b, c = "x" * 200, "y" * 200, "z" * 400  # ~50, ~50, ~100 tokens
    r1 = pack([a, b, c], budget_tokens=120)
    assert r1 == [[a, b], [c]], f"expected [a,b],[c]; got {r1}"

    r2 = pack([a, b], budget_tokens=1000)
    assert r2 == [[a, b]], f"all fit in one chunk; got {r2}"

    big = "q" * 4000  # ~1000 tokens, over budget alone -> its own chunk
    r3 = pack([a, big, b], budget_tokens=120)
    assert r3 == [[a], [big], [b]], f"oversized paragraph stands alone; got {r3}"

    assert all(sum(approx_tokens(p) for p in ch) <= 120 or len(ch) == 1 for ch in r1), "budget respected"
    print("PASS — heading-aware packing works (now imagine refusing to cross a section boundary)")


if __name__ == "__main__":
    _check()
