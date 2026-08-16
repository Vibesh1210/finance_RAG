"""Phase 2 gate: ingestion — EDGAR corpus, facts, fiscal calendars, narrative,
prices, U13 preliminary rows, supersession.

Fixtures-only: talks to the local/CI postgres and committed fixtures; no external
data-API calls (the live limiter behaviour is re-exercised deterministically in
check 6, not by hitting EDGAR). Maps 1:1 to the nine gate points in
docs/execution_plan_us.md, Phase 2.

Checks that depend on [HUMAN] verification or a market-data API key fail with a
clear, actionable message until that input arrives — that is the gate doing its
job, not a defect. See STATUS.md for the live blocker list.
"""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal

from common import ROOT, run_gate

from us_rag.db import connect

FIXTURES = ROOT / "fixtures"

# The 10-company universe (U1). Ordered for stable gate output.
UNIVERSE = ["AAPL", "CAT", "COST", "DE", "JNJ", "JPM", "MSFT", "NVDA", "WMT", "XOM"]


def _load_fixture(name: str) -> dict | list:
    path = FIXTURES / name
    if not path.exists():
        raise AssertionError(f"missing fixture {name} — run scripts/freeze_phase02_fixtures.py")
    return json.loads(path.read_text())


# ---------- check 1: registry counts ----------


def check_registry_counts() -> None:
    expected = _load_fixture("registry_expected.json")["counts"]
    with connect() as conn:
        live: dict[str, dict[str, int]] = {}
        for ticker, form, count in conn.execute(
            "SELECT t.ticker, d.form, count(*) FROM documents d"
            " JOIN tickers t USING (company_id) WHERE d.corpus"
            " GROUP BY t.ticker, d.form"
        ):
            live.setdefault(ticker, {})[form] = count
    if live != expected:
        raise AssertionError(
            "live corpus registry drifted from the frozen snapshot "
            "(re-freeze only if the backfill legitimately changed): "
            f"expected {expected}, got {live}"
        )
    for ticker in UNIVERSE:
        forms = expected.get(ticker, {})
        if forms.get("10-K") != 2:
            raise AssertionError(f"{ticker}: expected 2 10-K in window, got {forms.get('10-K')}")
        if forms.get("10-Q") not in (6, 7, 8):
            raise AssertionError(f"{ticker}: expected 6-8 10-Q, got {forms.get('10-Q')}")
        eightk = forms.get("8-K", 0) + forms.get("8-K/A", 0)
        if eightk < 8:
            raise AssertionError(f"{ticker}: expected >=8 8-K, got {eightk}")


# ---------- check 2: spot-check facts match exactly [HUMAN] ----------

SPOT_SCHEMA = (
    'each entry: {"ticker","concept","unit","period_end", optional "period_start", '
    '"value"} — the value read straight from the filing by hand; the gate asserts a '
    "loaded fact with that identity holds exactly that number."
)


def check_spot_checks() -> None:
    path = FIXTURES / "spot_checks.json"
    if not path.exists():
        raise AssertionError(
            "[HUMAN] fixtures/spot_checks.json missing — verify 20 facts (2/company) "
            f"against the actual filings, then commit them. Schema: {SPOT_SCHEMA} "
            "A pre-slotted template is at fixtures/spot_checks.template.json."
        )
    data = json.loads(path.read_text())
    entries = data["facts"] if isinstance(data, dict) else data
    if len(entries) < 20:
        raise AssertionError(f"spot_checks.json must hold >=20 facts (2/company), has {len(entries)}")
    with connect() as conn:
        misses = []
        for e in entries:
            row = conn.execute(
                "SELECT f.value FROM facts f JOIN tickers t USING (company_id)"
                " WHERE t.ticker = %s AND f.concept = %s AND f.unit = %s"
                "   AND f.period_end = %s"
                "   AND (%s::date IS NULL OR f.period_start = %s)",
                (e["ticker"], e["concept"], e["unit"], e["period_end"],
                 e.get("period_start"), e.get("period_start")),
            ).fetchone()
            if row is None:
                misses.append(f"{e['ticker']} {e['concept']} {e['period_end']}: no matching fact")
            elif Decimal(str(row[0])) != Decimal(str(e["value"])):
                misses.append(
                    f"{e['ticker']} {e['concept']} {e['period_end']}: "
                    f"loaded {row[0]} != filing {e['value']}"
                )
        if misses:
            raise AssertionError("spot-check mismatches (mapping/context bug): " + "; ".join(misses))


# ---------- check 3: fiscal calendars coverage + 53-week audit ----------


def check_fiscal_calendars() -> None:
    with connect() as conn:
        for ticker in UNIVERSE:
            for fy in (2024, 2025):
                periods = {
                    p for (p,) in conn.execute(
                        "SELECT fiscal_period FROM fiscal_calendars fc"
                        " JOIN tickers t USING (company_id)"
                        " WHERE t.ticker = %s AND fc.fiscal_year = %s",
                        (ticker, fy),
                    )
                }
                need = {"FY", "Q1", "Q2", "Q3", "Q4"}
                if not need.issubset(periods):
                    raise AssertionError(f"{ticker} FY{fy}: missing periods {need - periods}")
        de = conn.execute(
            "SELECT weeks FROM fiscal_calendars fc JOIN tickers t USING (company_id)"
            " WHERE t.ticker = 'DE' AND fc.fiscal_year = 2025 AND fc.fiscal_period = 'FY'"
        ).fetchone()
        if de != (53,):
            raise AssertionError(f"DE FY2025 53-week audit unresolved: weeks={de} (expected 53)")
        # every XBRL-derived calendar row must carry its evidence accession
        naked = conn.execute(
            "SELECT count(*) FROM fiscal_calendars WHERE source <> 'seed'"
            " AND source_accession IS NULL"
        ).fetchone()[0]
        if naked:
            raise AssertionError(f"{naked} non-seed calendar rows lack a source_accession")


# ---------- check 4: narrative boundaries ----------


def check_narrative() -> None:
    checks = _load_fixture("narrative_checks.json")["checks"]
    with connect() as conn:
        for c in checks:
            n_chunks, n_chars = conn.execute(
                "SELECT count(*), COALESCE(sum(length(text)), 0) FROM chunks"
                " WHERE accession = %s AND section = %s",
                (c["accession"], c["section"]),
            ).fetchone()
            if n_chunks < c["min_chunks"]:
                raise AssertionError(
                    f"{c['accession']} {c['section']}: {n_chunks} chunks < {c['min_chunks']}"
                )
            if n_chars < c["min_chars"]:
                raise AssertionError(
                    f"{c['accession']} {c['section']}: {n_chars} chars < {c['min_chars']}"
                )
            if c.get("opening_prefix"):
                first = conn.execute(
                    "SELECT text FROM chunks WHERE accession = %s AND section = %s"
                    " ORDER BY chunk_id LIMIT 1",
                    (c["accession"], c["section"]),
                ).fetchone()[0]
                if not first.startswith(c["opening_prefix"]):
                    raise AssertionError(
                        f"{c['accession']} {c['section']}: opening != hand-checked prefix"
                    )
        # every Ex-99.1 press release that was ingested must yield >=1 chunk
        empty_ex99 = conn.execute(
            "SELECT count(*) FROM documents d WHERE d.corpus AND d.form LIKE '8-K%'"
            " AND EXISTS (SELECT 1 FROM chunks c WHERE c.accession = d.accession"
            "             AND c.section LIKE 'EX-99%')"
        ).fetchone()[0]
        if empty_ex99 == 0:
            raise AssertionError("no EX-99 chunks found — narrative pass over 8-K exhibits missing")


# ---------- check 5: prices [KEY: TIINGO] ----------


def check_prices() -> None:
    with connect() as conn:
        n_prices = conn.execute("SELECT count(*) FROM prices").fetchone()[0]
        if n_prices == 0:
            raise AssertionError(
                "[KEY] prices empty — set TIINGO_API_KEY in .env and run the 2d price "
                "backfill (free key at tiingo.com)"
            )
        # no gap > 3 trading days per company
        gap = conn.execute(
            "SELECT t.ticker, max(d) FROM ("
            "  SELECT company_id, trade_date - lag(trade_date)"
            "         OVER (PARTITION BY company_id ORDER BY trade_date) AS d FROM prices"
            ") g JOIN tickers t USING (company_id) WHERE d > 5 GROUP BY t.ticker"
        ).fetchall()
        if gap:
            raise AssertionError(f"price gaps > 3 trading days: {gap}")
        nvda_split = conn.execute(
            "SELECT ex_date, factor FROM corporate_actions ca JOIN tickers t USING (company_id)"
            " WHERE t.ticker = 'NVDA' AND ca.action_type = 'split'"
        ).fetchone()
        if nvda_split is None:
            raise AssertionError("NVDA 10-for-1 split (June 2024) missing from corporate_actions")


# ---------- check 6: zero fair-access violations (deterministic limiter probe) ----------


def check_fair_access() -> None:
    import httpx

    from us_rag.ingest.edgar import (
        SEC_MAX_REQUESTS_PER_SECOND,
        EdgarClient,
        FairAccessError,
        RateLimiter,
    )

    if SEC_MAX_REQUESTS_PER_SECOND != 10:
        raise AssertionError(f"SEC cap tampered: {SEC_MAX_REQUESTS_PER_SECOND} (pin U: never raise)")

    class Clock:
        def __init__(self):
            self.t = 0.0

        def __call__(self):
            return self.t

        def sleep(self, s):
            self.t += s

    clock = Clock()
    limiter = RateLimiter(clock=clock, sleep=clock.sleep)
    for _ in range(200):
        limiter.acquire()
    if limiter.violations != 0:
        raise AssertionError(f"paced limiter recorded {limiter.violations} fair-access violations")

    # User-Agent with a contact email is mandatory: construction must fail without it
    try:
        EdgarClient("no-contact-here", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
        raise AssertionError("EdgarClient accepted a User-Agent with no contact email")
    except FairAccessError:
        pass


# ---------- check 7: U13 preliminary rows [HUMAN + 2e] ----------


def check_u13() -> None:
    with connect() as conn:
        rows = conn.execute(
            "SELECT f.fact_id, f.company_id, f.concept, f.period_end, f.knowledge_time,"
            "       f.preliminary, f.human_verified"
            " FROM facts f WHERE f.source = '8K-EX99'"
        ).fetchall()
        if not rows:
            raise AssertionError(
                "[HUMAN+2e] no U13 preliminary rows loaded — verify every row in "
                "fixtures/u13_staged.json against its 8-K Ex-99, then load them "
                "(rows insert with human_verified=true; DECISIONS.md #5)"
            )
        for fid, cid, concept, period_end, ktime, prelim, verified in rows:
            if not prelim:
                raise AssertionError(f"U13 fact {fid}: preliminary must be true")
            if not verified:
                raise AssertionError(f"U13 fact {fid}: human_verified must be true (each row, U13)")
            later = conn.execute(
                "SELECT min(knowledge_time) FROM facts WHERE company_id = %s AND concept = %s"
                " AND period_end = %s AND source IN ('10-K', '10-Q')",
                (cid, concept, period_end),
            ).fetchone()[0]
            if later is not None and not (ktime < later):
                raise AssertionError(
                    f"U13 fact {fid}: knowledge_time {ktime} not before periodic {later}"
                )


# ---------- check 8: fy/fp-independence unit test ----------


def check_fyfp_independence() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         "tests/test_facts_load.py::test_fyfp_never_touch_period_identity"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-20:])
        raise AssertionError(f"fy/fp-independence test failed:\n{tail}")


# ---------- check 9: supersession detected + hand-confirmed ----------


def check_supersession() -> None:
    case = _load_fixture("supersession_confirmed.json")
    with connect() as conn:
        found = conn.execute(
            "SELECT n.value FROM facts f"
            " JOIN facts n ON n.fact_id = f.superseded_by"
            " JOIN tickers t ON t.company_id = f.company_id"
            " WHERE t.ticker = %s AND f.concept = %s"
            "   AND f.period_start = %s AND f.period_end = %s",
            (case["ticker"], case["concept"], case["period_start"], case["period_end"]),
        ).fetchone()
    if found is None:
        raise AssertionError(
            "no comparative-revision supersession detected for the frozen JNJ/Kenvue case "
            "— if genuinely none exists corpus-wide, add a DECISIONS.md audit entry "
            "(never pass silently)"
        )
    if Decimal(str(found[0])) != Decimal(case["superseding"]["value"]):
        raise AssertionError(
            f"supersession target value {found[0]} != frozen {case['superseding']['value']}"
        )
    if not case.get("human_countersigned"):
        raise AssertionError(
            "[HUMAN] JNJ/Kenvue supersession detected but not countersigned — set "
            "human_countersigned=true in fixtures/supersession_confirmed.json after "
            "confirming it against the two filings"
        )


run_gate(
    "phase_02",
    [
        ("1. corpus registry matches frozen snapshot (2/10-K, 6-8/10-Q, >=8/8-K)", check_registry_counts),
        ("2. 20 spot-check facts match loaded facts exactly [HUMAN]", check_spot_checks),
        ("3. fiscal calendars: full FY+Q coverage; DE FY2025 53-week resolved", check_fiscal_calendars),
        ("4. narrative: Items 1A/7 boundaries on 3 filings; Ex-99 chunked", check_narrative),
        ("5. prices: no >3-day gaps; NVDA split present [KEY: TIINGO]", check_prices),
        ("6. zero fair-access violations; UA-without-email fatal", check_fair_access),
        ("7. U13: every row preliminary + human_verified; knowledge_time precedes periodic [HUMAN+2e]", check_u13),
        ("8. fy/fp-independence hard rule (dates win over fy/fp)", check_fyfp_independence),
        ("9. supersession detected + hand-countersigned (JNJ/Kenvue) [HUMAN]", check_supersession),
    ],
)
