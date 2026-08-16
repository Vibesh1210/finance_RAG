"""Phase 4 exercise — the metric registry resolver.

Implement resolve(): given the registry rows for one metric and a company id, return the
tag to read — following the rules:
  * a company-specific row beats the default row (company is None on the default),
  * a row whose tag is None means ABSTAIN (return the string "ABSTAIN"),
  * if nothing applies at all, return None.

Run:  uv run python learn/exercises/phase04_resolve_exercise.py
Goal: every check prints PASS. Peek at src/us_rag/query/metrics.py (pick_mapping) if stuck.
"""


def resolve(rows: list[dict], company_id: int) -> str | None:
    """rows: dicts like {"company": None or int, "tag": "Revenues" or None}.
    Return the chosen tag, or "ABSTAIN" if the chosen row's tag is None, or None."""
    # TODO: your turn. Consider only rows for this company or the default; company wins.
    raise NotImplementedError


# ---- self-checks (do not edit) ----
def _check():
    default_only = [{"company": None, "tag": "Revenues"}]
    assert resolve(default_only, 5) == "Revenues", "default applies when no override"

    with_override = [{"company": None, "tag": "Revenues"},
                     {"company": 5, "tag": "RevenueFromContract"}]
    assert resolve(with_override, 5) == "RevenueFromContract", "company override wins"
    assert resolve(with_override, 9) == "Revenues", "other companies fall back to default"

    bank = [{"company": None, "tag": "GrossProfit"}, {"company": 7, "tag": None}]
    assert resolve(bank, 7) == "ABSTAIN", "a None tag for this company means abstain"
    assert resolve(bank, 3) == "GrossProfit", "other companies still get the default"

    assert resolve([], 1) is None, "nothing applies -> None"
    print("PASS — company beats default, and a null mapping means abstain")


if __name__ == "__main__":
    _check()
