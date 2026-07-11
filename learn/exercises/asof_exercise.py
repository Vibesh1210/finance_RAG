"""Exercise 1: implement the as-of rule — the heart of Phase 1 — in pure Python.

The story (same as our real system, simplified):
Each record is something we learned, with:
    value        - the number we learned
    learned_on   - the day we learned it (knowledge_time)
    replaced_by  - index of the record that supersedes it, or None

THE RULE (this is the whole bitemporal idea):
    A record is visible on day T if:
      1. we had learned it by then:  learned_on <= T
      2. AND it wasn't yet replaced: replaced_by is None,
         OR the replacing record's learned_on is AFTER T
    (Replacement chains work automatically: each record only needs to check
     the one record that replaces it.)

Implement what_was_known(). Run this file; the checks tell you if you're right:

    uv run python learn/exercises/asof_exercise.py

Stuck? Read the SQL in src/us_rag/store/asof.py and translate it. Don't copy —
the point is writing the rule yourself once.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class Record:
    value: str
    learned_on: date
    replaced_by: int | None  # index into RECORDS, or None


# NVIDIA Q3 revenue, as the world learned it:
RECORDS = [
    Record("$35.08B (preliminary, press release)", date(2024, 11, 20), replaced_by=1),
    Record("$35.082B (final, 10-Q)", date(2024, 12, 1), replaced_by=2),
    Record("$35.9B (imaginary restatement)", date(2026, 3, 1), replaced_by=None),
]


def what_was_known(records: list[Record], as_of: date) -> list[str]:
    """Return the values visible on day `as_of`, applying THE RULE above."""
    raise NotImplementedError("your code here (~5-10 lines)")


CHECKS = [
    (date(2024, 11, 19), []),                                    # nothing known yet
    (date(2024, 11, 20), ["$35.08B (preliminary, press release)"]),
    (date(2024, 11, 25), ["$35.08B (preliminary, press release)"]),  # the look-ahead trap day
    (date(2024, 12, 1), ["$35.082B (final, 10-Q)"]),
    (date(2025, 6, 1), ["$35.082B (final, 10-Q)"]),
    (date(2026, 4, 1), ["$35.9B (imaginary restatement)"]),      # chains compose
]

if __name__ == "__main__":
    try:
        what_was_known(RECORDS, CHECKS[0][0])
    except NotImplementedError:
        raise SystemExit(
            "Not implemented yet — open this file and write what_was_known(). "
            "Re-run when ready."
        )
    failures = 0
    for as_of, expected in CHECKS:
        got = what_was_known(RECORDS, as_of)
        if got == expected:
            print(f"  PASS  as of {as_of}: {got or '(nothing known)'}")
        else:
            failures += 1
            print(f"  FAIL  as of {as_of}: expected {expected}, got {got}")
    if failures:
        print(f"\n{failures} check(s) failing — keep going, re-read THE RULE.")
    else:
        print("\nAll checks pass. You just implemented a bitemporal as-of query.")
        print("Compare your rule with the SQL in src/us_rag/store/asof.py — same shape?")
