"""Look-ahead logic unit tests (pure: no DB, no model). The live-corpus scan is
exercised by the Phase 3 gate; here we pin the cutoff semantics and the violation
filter that the gate relies on."""

from __future__ import annotations

from datetime import date, datetime, timezone

from us_rag.eval.lookahead import to_cutoff, violations_in

UTC = timezone.utc


def test_to_cutoff_maps_date_to_midnight_utc():
    # mirrors Postgres coercing `knowledge_time <= '2024-04-28'` to that date at 00:00
    assert to_cutoff(date(2024, 4, 28)) == datetime(2024, 4, 28, tzinfo=UTC)


def test_to_cutoff_passes_datetime_through():
    dt = datetime(2024, 4, 28, 15, 30, tzinfo=UTC)
    assert to_cutoff(dt) == dt


def test_violations_in_flags_only_strictly_future():
    cutoff = datetime(2024, 4, 28, tzinfo=UTC)
    hits = [
        (1, datetime(2024, 4, 25, 20, 0, tzinfo=UTC)),  # before -> ok
        (2, datetime(2024, 5, 1, 20, 0, tzinfo=UTC)),   # after  -> violation
        (3, datetime(2024, 4, 28, 0, 0, tzinfo=UTC)),   # exactly at cutoff -> ok (not >)
    ]
    assert [cid for cid, _ in violations_in(hits, cutoff)] == [2]


def test_violations_in_clean():
    cutoff = datetime(2025, 1, 1, tzinfo=UTC)
    assert violations_in([(1, datetime(2024, 1, 1, tzinfo=UTC))], cutoff) == []
