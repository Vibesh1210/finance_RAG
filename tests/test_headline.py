"""U13 workflow tests (plan 2e), fixtures-only — no LLM API calls. The LLM's
output shape is simulated; what's tested is OUR half of the bargain: fail-closed
normalization, the verification gate, and the bitemporal shape of inserted rows."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from us_rag.ingest.headline import METRICS, normalize_value, stage_rows
from us_rag.units import UnitError

RELEASE = {
    "ticker": "NVDA",
    "accession": "U13-TEST-8K",
    "acceptance": "2025-02-26T16:20:00+00:00",
    "exhibit_path": "blobs/NVDA/U13-TEST-8K/pr.htm",
    "fiscal_year": 2025,
    "fiscal_period": "Q4",
    "period_start": "2024-10-28",
    "period_end": "2025-01-26",
    "next_periodic_acceptance": "2025-02-26T16:31:00+00:00",
}


def test_normalize_value_is_exact_and_fail_closed():
    assert normalize_value("revenue", "$39.3 billion") == Decimal("39300000000")
    assert normalize_value("revenue", "$14,881 million") == Decimal("14881000000")
    assert normalize_value("diluted_eps", "0.89") == Decimal("0.89")
    with pytest.raises(UnitError):
        normalize_value("revenue", "39,331")  # bare scalable number: never guessed
    with pytest.raises(UnitError):
        normalize_value("diluted_eps", "$0.89 million")  # per-share is scale-exempt


def test_stage_rows_normalizes_and_flags_failures():
    extraction = {
        "revenue": {"value_text": "$39.3 billion", "quote": "Revenue was $39.3 billion."},
        "net_income": {"value_text": "22,091", "quote": "Net income of 22,091."},  # bare!
        "diluted_eps": None,
        "note": "EPS not stated",
    }
    rows = {r["metric"]: r for r in stage_rows(RELEASE, extraction)}
    assert rows["revenue"]["value"] == "39300000000"
    assert rows["revenue"]["verified"] is False
    assert "normalizer rejected" in rows["net_income"]["error"]
    assert "not extracted" in rows["diluted_eps"]["error"]
    assert all(r["concept"] == METRICS[m][0] for m, r in rows.items())


def test_insert_shape_and_ordering(conn, company_id):
    """The row a verified staged entry becomes: preliminary, human_verified at
    insert, knowledge_time strictly before the matching periodic filing."""
    from us_rag.store.asof import insert_fact

    nvda = company_id("NVDA")
    acceptance = datetime(2025, 2, 26, 16, 20, tzinfo=timezone.utc)
    conn.execute(
        "INSERT INTO documents (accession, company_id, form, filed_date,"
        " acceptance_datetime, status, corpus)"
        " VALUES ('U13-TEST-8K', %s, '8-K', '2025-02-26', %s, 'fetched', true)",
        (nvda, acceptance),
    )
    fact_id = insert_fact(
        conn,
        company_id=nvda,
        concept="Revenues",
        axis=None,
        member=None,
        value=Decimal("39300000000"),
        unit="USD",
        period_start="2024-10-28",
        period_end="2025-01-26",
        period_kind="duration",
        knowledge_time=acceptance,
        accession="U13-TEST-8K",
        source="8K-EX99",
        preliminary=True,
        human_verified=True,
    )
    row = conn.execute(
        "SELECT preliminary, human_verified, knowledge_time FROM facts WHERE fact_id = %s",
        (fact_id,),
    ).fetchone()
    assert row[0] is True and row[1] is True
    # the canonical point-in-time window: preliminary knowledge precedes the 10-K
    ten_k = datetime(2025, 2, 26, 16, 31, tzinfo=timezone.utc)
    assert row[2] < ten_k
