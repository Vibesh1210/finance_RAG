"""EDGAR client + corpus selection tests. Network-free: CI runs these (fixtures-only
rule) — live behavior is exercised by the local backfill, whose limiter counters the
Phase 2 gate audits."""

from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest

from us_rag.ingest.backfill import (
    CorpusError,
    annual_windows,
    corpus_bounds,
    select_corpus,
)
from us_rag.ingest.edgar import (
    EdgarClient,
    FairAccessError,
    Filing,
    RateLimiter,
    _parse_filing_block,
    archive_url,
    parse_ex99_entries,
)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


# ---------- rate limiter ----------


def test_limiter_paces_below_cap():
    clock = FakeClock()
    limiter = RateLimiter(clock=clock, sleep=clock.sleep)
    for _ in range(40):
        limiter.acquire()
    assert limiter.sent == 40
    assert limiter.violations == 0
    # 40 sends at 8/s must span at least ~4.8 simulated seconds
    assert clock.t >= 39 / 8 - 1e-9


def test_limiter_counts_violations_honestly():
    # a sleep that does NOT advance time simulates pacing failure: the sliding
    # window must then MEASURE the breach instead of assuming it away
    clock = FakeClock()
    limiter = RateLimiter(clock=clock, sleep=lambda s: None)
    for _ in range(12):
        limiter.acquire()
    assert limiter.violations > 0


# ---------- client construction + retry behavior ----------


def test_user_agent_without_email_is_fatal(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "no-contact-here")
    with pytest.raises(FairAccessError):
        EdgarClient()


def _fast_client(handler) -> tuple[EdgarClient, list]:
    clock = FakeClock()
    sleeps: list[float] = []

    def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    client = EdgarClient(
        "us-rag-tests test@example.com",
        transport=httpx.MockTransport(handler),
        limiter=RateLimiter(clock=clock, sleep=clock.sleep),
        sleep=record_sleep,
    )
    return client, sleeps


def test_retry_after_is_honored():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={"ok": True})

    client, sleeps = _fast_client(handler)
    assert client.get_json("https://data.sec.gov/anything.json") == {"ok": True}
    assert 7 in sleeps
    assert client.limiter.retry_after_honored == 1


def test_gives_up_after_bounded_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client, _ = _fast_client(handler)
    with pytest.raises(FairAccessError):
        client.get("https://data.sec.gov/broken.json")


def test_non_retryable_status_raises_immediately():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    client, _ = _fast_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("https://data.sec.gov/missing.json")
    assert len(calls) == 1


# ---------- parsing ----------


def test_parse_filing_block_columnar():
    block = {
        "accessionNumber": ["0000320193-24-000123", "0000320193-24-000069"],
        "form": ["10-K", "8-K"],
        "filingDate": ["2024-11-01", "2024-08-01"],
        "reportDate": ["2024-09-28", ""],
        "acceptanceDateTime": ["2024-11-01T18:01:14.000Z", "2024-08-01T16:30:00.000Z"],
        "primaryDocument": ["aapl-20240928.htm", "aapl-8k.htm"],
        "items": ["", "2.02,9.01"],
    }
    filings = _parse_filing_block(block)
    assert filings[0].report_date == date(2024, 9, 28)
    assert filings[0].acceptance == datetime(2024, 11, 1, 18, 1, 14, tzinfo=timezone.utc)
    assert filings[1].report_date is None
    assert filings[1].items == "2.02,9.01"


def test_parse_ex99_filenames_from_index_page():
    html = """
    <table class="tableFile" summary="Document Format Files">
    <tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th></tr>
    <tr><td>1</td><td>8-K BODY</td>
        <td><a href="/Archives/edgar/data/1045810/000104581025000023/nvda-body.htm">nvda-body.htm</a></td>
        <td>8-K</td></tr>
    <tr><td>2</td><td>PRESS RELEASE</td>
        <td><a href="/Archives/edgar/data/1045810/000104581025000023/q4fy25pr.htm">q4fy25pr.htm</a></td>
        <td> EX-99.1</td></tr>
    <tr><td>3</td><td>CFO COMMENTARY</td>
        <td><a href="/Archives/edgar/data/1045810/000104581025000023/cfo.htm">cfo.htm</a></td>
        <td>EX-99.2</td></tr>
    <tr><td>4</td><td>GRAPHIC</td>
        <td><a href="/Archives/edgar/data/1045810/000104581025000023/chart.jpg">chart.jpg</a></td>
        <td>GRAPHIC</td></tr>
    </table>
    """
    assert parse_ex99_entries(html) == [("EX-99.1", "q4fy25pr.htm"), ("EX-99.2", "cfo.htm")]


def test_archive_url_uses_unpadded_cik_and_nodash_accession():
    url = archive_url("0000320193", "0000320193-24-000123", "aapl-20240928.htm")
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019324000123/aapl-20240928.htm"
    )


# ---------- corpus selection ----------


def _cf_with_windows(*windows: tuple[str, str]) -> dict:
    entries = [
        {"start": start, "end": end, "val": 1, "form": "10-K", "accn": f"a{i}"}
        for i, (start, end) in enumerate(windows)
    ]
    return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": entries}}}}}


def test_annual_windows_labels_by_end_year_and_votes():
    cf = _cf_with_windows(
        ("2023-01-30", "2024-01-28"),
        ("2023-01-30", "2024-01-28"),  # re-reported comparative: two votes
        ("2024-01-29", "2025-01-26"),
    )
    windows = annual_windows(cf)
    assert windows[2024] == (date(2023, 1, 30), date(2024, 1, 28))
    assert windows[2025] == (date(2024, 1, 29), date(2025, 1, 26))


def _filing(form: str, report: str | None, accepted: str, accession: str) -> Filing:
    return Filing(
        accession=accession,
        form=form,
        filing_date=date.fromisoformat(accepted[:10]),
        report_date=date.fromisoformat(report) if report else None,
        acceptance=datetime.fromisoformat(accepted).replace(tzinfo=timezone.utc),
        primary_document=f"{accession}.htm",
        items="",
    )


def test_select_corpus_window_and_close():
    fy_start, fy_end = date(2023, 1, 30), date(2025, 1, 26)
    filings = [
        _filing("10-K", "2023-01-29", "2023-02-24T16:00:00", "old-10k"),  # FY2023: out
        _filing("10-K", "2024-01-28", "2024-02-21T16:00:00", "fy24-10k"),
        _filing("10-Q", "2024-04-28", "2024-05-29T16:00:00", "q1-10q"),
        _filing("10-K", "2025-01-26", "2025-02-26T16:31:00", "fy25-10k"),
        # Q4 FY2025 earnings 8-K: AFTER fiscal year end, BEFORE the 10-K — must be in
        _filing("8-K", None, "2025-02-26T16:20:00", "q4-8k"),
        # 8-K after the corpus close — out
        _filing("8-K", None, "2025-05-28T16:20:00", "post-8k"),
        _filing("8-K", None, "2024-08-28T16:20:00", "mid-8k"),
    ]
    sel = select_corpus(filings, fy_start, fy_end)
    periodic = {f.accession for f in sel.periodic}
    events = {f.accession for f in sel.events}
    assert periodic == {"fy24-10k", "q1-10q", "fy25-10k"}
    assert events == {"q4-8k", "mid-8k"}
    assert sel.close == date(2025, 2, 26)


def test_select_corpus_requires_fy2025_10k():
    filings = [_filing("10-Q", "2024-04-28", "2024-05-29T16:00:00", "q1-10q")]
    with pytest.raises(CorpusError):
        select_corpus(filings, date(2023, 1, 30), date(2025, 1, 26))


def test_corpus_bounds_cross_checks_seeds(conn, company_id):
    nvda = company_id("NVDA")
    good = _cf_with_windows(("2023-01-30", "2024-01-28"), ("2024-01-29", "2025-01-26"))
    assert corpus_bounds(conn, nvda, good) == (date(2023, 1, 30), date(2025, 1, 26))
    # a derivation that disagrees with the seeded calendar must fail closed
    bad = _cf_with_windows(("2023-02-01", "2024-01-31"), ("2024-02-01", "2025-01-31"))
    with pytest.raises(CorpusError):
        corpus_bounds(conn, nvda, bad)
