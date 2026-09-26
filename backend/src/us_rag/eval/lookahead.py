"""The look-ahead gate (design §6.5, §9) — the cardinal rule of the whole system:
retrieval must NEVER surface a chunk newer than the query's as_of. Leaking future
information into a historical answer is the one unforgivable finance bug.

`scan` runs REAL retrieval (both legs, real query embeddings) for each golden question
at its as_of and reports any chunk whose knowledge_time is after that as_of. The teeth
come from the point-in-time questions: the later 10-Q is highly relevant, so if the
as-of pushdown ever regressed, that future filing would rank high and this gate would
catch the leak. `meaningful` counts how many questions actually have future chunks to
exclude, so the gate also fails if the historical-as-of samples ever disappear (a
vacuously-passing test is worthless).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone

import psycopg

from us_rag.query.retrieve import LEG_K, dense_leg, sparse_leg


def to_cutoff(as_of: date | datetime) -> datetime:
    """The retriever passes a date to `knowledge_time <= %s`, which Postgres reads as
    that date at 00:00 UTC. Mirror that exactly so the check matches the filter."""
    if isinstance(as_of, datetime):
        return as_of
    return datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)


def violations_in(
    hits: Sequence[tuple[int, datetime]], cutoff: datetime
) -> list[tuple[int, datetime]]:
    """Pure: the (chunk_id, knowledge_time) pairs strictly newer than cutoff."""
    return [(cid, kt) for cid, kt in hits if kt > cutoff]


@dataclass(frozen=True)
class Leak:
    qid: str
    as_of: date | datetime
    chunk_id: int
    knowledge_time: datetime
    leg: str


def _hydrate(conn: psycopg.Connection, ids: list[int]) -> list[tuple[int, datetime]]:
    if not ids:
        return []
    return conn.execute(
        "SELECT chunk_id, knowledge_time FROM chunks WHERE chunk_id = ANY(%s)", [ids]
    ).fetchall()


def future_chunk_count(conn: psycopg.Connection, as_of: date | datetime) -> int:
    """How many chunks are newer than as_of — how much the filter must exclude. Zero
    means the look-ahead test is vacuous at this as_of (nothing to catch)."""
    return conn.execute(
        "SELECT count(*) FROM chunks WHERE knowledge_time > %s", [as_of]
    ).fetchone()[0]


def scan(
    conn: psycopg.Connection, questions, embed_fn: Callable[[str], list[float]]
) -> tuple[list[Leak], int]:
    """Return (leaks, meaningful). Checks both legs with the real as-of pushdown across
    the whole (broadest, no company scope) corpus — the widest net for a leak."""
    leaks: list[Leak] = []
    meaningful = 0
    for q in questions:
        cutoff = to_cutoff(q.as_of)
        if future_chunk_count(conn, q.as_of) > 0:
            meaningful += 1
        legs = (
            ("dense", dense_leg(conn, embed_fn(q.question), q.as_of, k=LEG_K)),
            ("sparse", sparse_leg(conn, q.question, q.as_of, k=LEG_K)),
        )
        for leg, ids in legs:
            for cid, kt in violations_in(_hydrate(conn, ids), cutoff):
                leaks.append(Leak(q.id, q.as_of, cid, kt, leg))
    return leaks, meaningful
