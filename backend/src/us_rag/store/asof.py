"""Bitemporal reads and the sanctioned write paths for `facts` (design §4.2, U11).

AsOfContext is the ONLY sanctioned way to read facts/chunks. As-of semantics:
a query at time T sees rows with knowledge_time <= T, excluding rows whose
superseding row was itself known by T. Supersession chains compose naturally.

Writes: insert_fact() appends; supersede() sets the write-once superseded_by link
(the single UPDATE the DB trigger permits — anything else raises).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

_FACT_COLS = (
    "company_id, concept, axis, member, value, unit, period_start, period_end, "
    "period_kind, knowledge_time, accession, source, preliminary, human_verified"
)


@dataclass(frozen=True)
class AsOfContext:
    conn: psycopg.Connection
    as_of: datetime

    def facts(
        self,
        *,
        company_id: int | None = None,
        concept: str | None = None,
        period_end: Any | None = None,
        axis: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["f.knowledge_time <= %(as_of)s",
                      "(f.superseded_by IS NULL OR sup.knowledge_time > %(as_of)s)"]
        params: dict[str, Any] = {"as_of": self.as_of}
        if company_id is not None:
            conditions.append("f.company_id = %(company_id)s")
            params["company_id"] = company_id
        if concept is not None:
            conditions.append("f.concept = %(concept)s")
            params["concept"] = concept
        if period_end is not None:
            conditions.append("f.period_end = %(period_end)s")
            params["period_end"] = period_end
        if axis is not None:
            conditions.append("f.axis = %(axis)s")
            params["axis"] = axis
        sql = (
            "SELECT f.* FROM facts f"
            " LEFT JOIN facts sup ON sup.fact_id = f.superseded_by"
            f" WHERE {' AND '.join(conditions)}"
            " ORDER BY f.period_end, f.knowledge_time, f.fact_id"
        )
        with self.conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(sql, params).fetchall()

    def chunks(
        self,
        *,
        company_id: int | None = None,
        section: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["knowledge_time <= %(as_of)s"]
        params: dict[str, Any] = {"as_of": self.as_of}
        if company_id is not None:
            conditions.append("company_id = %(company_id)s")
            params["company_id"] = company_id
        if section is not None:
            conditions.append("section = %(section)s")
            params["section"] = section
        sql = (
            "SELECT chunk_id, accession, company_id, doc_type, section, fiscal_context,"
            " knowledge_time, text FROM chunks"
            f" WHERE {' AND '.join(conditions)} ORDER BY knowledge_time, chunk_id"
        )
        with self.conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(sql, params).fetchall()


def insert_fact(conn: psycopg.Connection, **cols: Any) -> int:
    placeholders = ", ".join(f"%({c.strip()})s" for c in _FACT_COLS.split(","))
    row = conn.execute(
        f"INSERT INTO facts ({_FACT_COLS}) VALUES ({placeholders}) RETURNING fact_id",
        {c.strip(): cols.get(c.strip()) for c in _FACT_COLS.split(",")},
    ).fetchone()
    return row[0]


def supersede(conn: psycopg.Connection, old_fact_id: int, new_fact_id: int) -> None:
    """Link old→new. Both rows must describe the same logical fact; the DB trigger
    additionally enforces that this link is set at most once and nothing else changes."""
    with conn.cursor(row_factory=dict_row) as cur:
        def fetch(fact_id: int) -> dict[str, Any]:
            row = cur.execute(
                "SELECT company_id, concept, axis, member, unit, period_start,"
                " period_end, period_kind, knowledge_time FROM facts WHERE fact_id = %s",
                (fact_id,),
            ).fetchone()
            if row is None:
                raise LookupError(f"fact {fact_id} does not exist")
            return row

        old, new = fetch(old_fact_id), fetch(new_fact_id)
    identity_keys = ("company_id", "concept", "axis", "member", "unit",
                     "period_start", "period_end", "period_kind")
    if any(old[k] != new[k] for k in identity_keys):
        raise ValueError(
            f"supersede({old_fact_id}→{new_fact_id}): rows are not the same logical fact"
        )
    if new["knowledge_time"] < old["knowledge_time"]:
        raise ValueError("superseding row cannot be known earlier than the row it supersedes")
    # the single sanctioned UPDATE on facts (write-once; enforced by trigger)
    conn.execute(
        "UPDATE facts SET superseded_by = %s WHERE fact_id = %s",
        (new_fact_id, old_fact_id),
    )
