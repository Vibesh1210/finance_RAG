"""EDGAR client (design §3.1). Fair access is enforced by construction:

- the send rate is paced BELOW the SEC's 10 req/s rule, and a sliding 1-second
  window *measures* what was actually sent (the Phase 2 gate asserts zero
  violations from these counters — measured, not assumed);
- the User-Agent with a contact email is mandatory: construction fails without it;
- 403/429/5xx honor Retry-After, back off exponentially otherwise; retries bounded.

The cap is a module constant on purpose — there is no configuration path that can
raise it (CLAUDE.md hard rule). Blob caching lives in backfill.py; this module is
pure HTTP + EDGAR URL/JSON conventions.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import httpx

from us_rag.env import load_env

SEC_MAX_REQUESTS_PER_SECOND = 10  # SEC fair-access rule — never raise
_SEND_INTERVAL = 1.0 / 8  # pace at 8/s, deliberately under the cap
_MAX_TRIES = 5
_RETRYABLE = {403, 429, 500, 502, 503, 504}

DATA_HOST = "https://data.sec.gov"
ARCHIVE_HOST = "https://www.sec.gov"


class FairAccessError(RuntimeError):
    """A request could not be made (or completed) within fair-access rules."""


def cik_path(cik: str) -> str:
    """Archive paths use the unpadded CIK ('320193'), APIs the padded one."""
    return str(int(cik))


def accession_nodash(accession: str) -> str:
    return accession.replace("-", "")


def submissions_url(cik: str) -> str:
    return f"{DATA_HOST}/submissions/CIK{cik}.json"


def submissions_page_url(name: str) -> str:
    return f"{DATA_HOST}/submissions/{name}"


def companyfacts_url(cik: str) -> str:
    return f"{DATA_HOST}/api/xbrl/companyfacts/CIK{cik}.json"


def archive_url(cik: str, accession: str, filename: str) -> str:
    return f"{ARCHIVE_HOST}/Archives/edgar/data/{cik_path(cik)}/{accession_nodash(accession)}/{filename}"


def filing_index_url(cik: str, accession: str) -> str:
    return archive_url(cik, accession, f"{accession}-index.htm")


@dataclass(frozen=True)
class Filing:
    """One row of a company's submissions index."""

    accession: str
    form: str
    filing_date: date
    report_date: date | None  # the period the filing reports on; None on some 8-Ks
    acceptance: datetime  # authoritative knowledge_time source (design §4.2)
    primary_document: str
    items: str  # 8-K item codes ('2.02,9.01'); '' for other forms


class RateLimiter:
    """Paces sends to _SEND_INTERVAL and measures the actual rate.

    Enforcement is the interval; the sliding window exists so violations are
    *counted* rather than assumed impossible — the gate reads these counters.
    """

    def __init__(self, clock=time.monotonic, sleep=time.sleep):
        self._clock, self._sleep = clock, sleep
        self._window: deque[float] = deque()
        self._last: float | None = None
        self.sent = 0
        self.violations = 0
        self.retry_after_honored = 0
        self.backoffs = 0

    def acquire(self) -> None:
        now = self._clock()
        if self._last is not None:
            wait = self._last + _SEND_INTERVAL - now
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
        cutoff = now - 1.0
        while self._window and self._window[0] <= cutoff:
            self._window.popleft()
        if len(self._window) >= SEC_MAX_REQUESTS_PER_SECOND:
            self.violations += 1  # unreachable by construction; counted honestly if not
        self._window.append(now)
        self._last = now
        self.sent += 1

    def stats(self) -> dict:
        return {
            "sent": self.sent,
            "violations": self.violations,
            "retry_after_honored": self.retry_after_honored,
            "backoffs": self.backoffs,
        }


class EdgarClient:
    def __init__(
        self,
        user_agent: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        limiter: RateLimiter | None = None,
        sleep=time.sleep,
    ):
        load_env()
        ua = user_agent or os.environ.get("SEC_EDGAR_USER_AGENT", "")
        if "@" not in ua:
            raise FairAccessError(
                "SEC_EDGAR_USER_AGENT with a contact email is mandatory (design §3.1)"
            )
        self.limiter = limiter or RateLimiter()
        self._sleep = sleep
        self._client = httpx.Client(
            headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"},
            timeout=30.0,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "EdgarClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def get(self, url: str) -> httpx.Response:
        last_status = None
        for attempt in range(_MAX_TRIES):
            self.limiter.acquire()
            try:
                response = self._client.get(url)
            except httpx.TransportError:
                if attempt == _MAX_TRIES - 1:
                    raise
                self.limiter.backoffs += 1
                self._sleep(2**attempt)
                continue
            if response.status_code == 200:
                return response
            last_status = response.status_code
            if response.status_code not in _RETRYABLE:
                response.raise_for_status()
            if attempt < _MAX_TRIES - 1:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    self.limiter.retry_after_honored += 1
                    self._sleep(int(retry_after))
                else:
                    self.limiter.backoffs += 1
                    self._sleep(2**attempt)
        raise FairAccessError(f"gave up on {url} after {_MAX_TRIES} tries (last {last_status})")

    def get_json(self, url: str) -> dict:
        return self.get(url).json()

    # ---------- submissions ----------

    def all_filings(self, cik: str, *, back_to: date) -> tuple[list[Filing], dict]:
        """Full filing index back to `back_to`, following pagination as needed.

        Returns (filings, raw_pages) — raw pages are cached by backfill so later
        stages (facts loader) can resolve acceptance datetimes offline.
        """
        root = self.get_json(submissions_url(cik))
        pages = {"root": root}
        filings = _parse_filing_block(root["filings"]["recent"])
        for extra in root["filings"].get("files", []):
            if date.fromisoformat(extra["filingTo"]) < back_to:
                continue
            page = self.get_json(submissions_page_url(extra["name"]))
            pages[extra["name"]] = page
            filings.extend(_parse_filing_block(page))
        filings.sort(key=lambda f: f.acceptance)
        return filings, pages

    def companyfacts(self, cik: str) -> dict:
        return self.get_json(companyfacts_url(cik))

    # ---------- filing documents ----------

    def filing_file(self, cik: str, accession: str, filename: str) -> bytes:
        return self.get(archive_url(cik, accession, filename)).content

    def ex99_documents(self, cik: str, accession: str) -> list[tuple[str, str]]:
        """(exhibit type, filename) of EX-99.* HTML exhibits, from the EDGAR-generated
        index page (stable EDGAR HTML — never filer HTML, so a dumb parse is safe)."""
        html = self.get(filing_index_url(cik, accession)).text
        return parse_ex99_entries(html)


def _parse_filing_block(block: dict) -> list[Filing]:
    """submissions JSON is columnar (parallel arrays); zip it into Filing rows."""
    out = []
    for i in range(len(block["accessionNumber"])):
        report = block["reportDate"][i]
        out.append(
            Filing(
                accession=block["accessionNumber"][i],
                form=block["form"][i],
                filing_date=date.fromisoformat(block["filingDate"][i]),
                report_date=date.fromisoformat(report) if report else None,
                acceptance=datetime.fromisoformat(
                    block["acceptanceDateTime"][i].replace("Z", "+00:00")
                ),
                primary_document=block["primaryDocument"][i],
                items=block.get("items", [""] * len(block["accessionNumber"]))[i] or "",
            )
        )
    return out


_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_HREF_RE = re.compile(r'href="([^"]+?\.html?)"', re.IGNORECASE)
_EXTYPE_RE = re.compile(r">\s*(EX-99[.\d]*)\s*<")


def parse_ex99_entries(index_html: str) -> list[tuple[str, str]]:
    """(exhibit type, document name) pairs for EX-99.* HTML exhibits of a filing,
    out of an EDGAR filing index page, in page order."""
    entries: list[tuple[str, str]] = []
    for row in _ROW_RE.findall(index_html):
        type_match = _EXTYPE_RE.search(row)
        if not type_match:
            continue
        exhibit_type = type_match.group(1).strip().upper()
        for href in _HREF_RE.findall(row):
            name = href.split("/")[-1]  # basename; hrefs may be absolute or ix?doc= form
            if all(name != existing for _, existing in entries):
                entries.append((exhibit_type, name))
    return entries


def write_limiter_stats(limiter: RateLimiter, path: Path) -> None:
    """Accumulate limiter counters across runs; the gate reads this file."""
    totals = limiter.stats()
    if path.exists():
        previous = json.loads(path.read_text())
        for key in totals:
            totals[key] += previous.get(key, 0)
    totals["updated"] = datetime.now().astimezone().isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(totals, indent=2) + "\n")
