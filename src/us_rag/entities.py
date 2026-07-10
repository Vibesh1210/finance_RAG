"""Entity resolution (design §4.3, §6.6): alias/ticker/name → company.

Ambiguity is a first-class outcome: resolve() returns ALL candidates; a caller
that needs exactly one must handle len != 1 via the clarification policy — this
module never guesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class Candidate:
    company_id: int
    cik: str
    name: str
    matched_on: str  # 'ticker' | 'alias'


class UnknownEntityError(LookupError):
    pass


def resolve(
    conn: psycopg.Connection, text: str, *, as_of: date | None = None
) -> list[Candidate]:
    """Return all companies matching `text` as a ticker (point-in-time) or alias."""
    needle = text.strip()
    candidates: dict[int, Candidate] = {}
    with conn.cursor(row_factory=dict_row) as cur:
        ticker_rows = cur.execute(
            """
            SELECT c.company_id, c.cik, c.name FROM companies c
            JOIN tickers t USING (company_id)
            WHERE upper(t.ticker) = upper(%(needle)s)
              AND (%(as_of)s::date IS NULL
                   OR (t.valid_from <= %(as_of)s
                       AND (t.valid_to IS NULL OR t.valid_to > %(as_of)s)))
            """,
            {"needle": needle, "as_of": as_of},
        ).fetchall()
        for row in ticker_rows:
            candidates[row["company_id"]] = Candidate(
                row["company_id"], row["cik"], row["name"], "ticker"
            )
        alias_rows = cur.execute(
            """
            SELECT c.company_id, c.cik, c.name FROM companies c
            JOIN name_aliases a USING (company_id)
            WHERE lower(a.alias) = lower(%s)
            """,
            (needle,),
        ).fetchall()
        for row in alias_rows:
            candidates.setdefault(
                row["company_id"],
                Candidate(row["company_id"], row["cik"], row["name"], "alias"),
            )
    if not candidates:
        raise UnknownEntityError(f"no company matches {text!r}")
    return sorted(candidates.values(), key=lambda c: c.company_id)


def resolve_one(conn: psycopg.Connection, text: str, *, as_of: date | None = None) -> Candidate:
    """Exactly-one resolution; ambiguity raises — callers surface it, never guess."""
    matches = resolve(conn, text, as_of=as_of)
    if len(matches) > 1:
        names = ", ".join(c.name for c in matches)
        raise UnknownEntityError(f"{text!r} is ambiguous between: {names} — clarify")
    return matches[0]
