"""Freeze Phase 2 corpus expectations into committed fixtures (run ONCE after a
verified backfill; rerunning overwrites — the gate then holds the line).

Writes:
- fixtures/registry_expected.json     — per-company corpus registry counts (gate 1)
- fixtures/supersession_confirmed.json — the confirmed JNJ/Kenvue case (gate 9)
- fixtures/narrative_checks.json      — hand-checked section boundaries (gate 4)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "src"))

from us_rag.db import connect  # noqa: E402
from us_rag.env import repo_root  # noqa: E402

FIXTURES = repo_root() / "fixtures"

# The three filings whose Item 1A/7 boundaries were hand-checked on 2026-07-17
# (first ~60 chars of each section's opening paragraph, from the filings themselves).
HAND_CHECKED = {
    "0000320193-25-000079": {  # AAPL FY2025 10-K
        "Item 1A": "The following summarizes factors that could have a material",
        "Item 7": None,  # presence + size only; opening varies with layout
    },
    "0000950170-25-100235": {"Item 1A": None, "Item 7": None},  # MSFT FY2025 10-K
    "0001045810-25-000023": {"Item 1A": None, "Item 7": None},  # NVDA FY2025 10-K
}


def main() -> None:
    with connect() as conn:
        registry = {}
        for ticker, form, count in conn.execute(
            "SELECT t.ticker, d.form, count(*) FROM documents d"
            " JOIN tickers t USING (company_id) WHERE d.corpus"
            " GROUP BY t.ticker, d.form ORDER BY t.ticker, d.form"
        ):
            registry.setdefault(ticker, {})[form] = count
        (FIXTURES / "registry_expected.json").write_text(
            json.dumps(
                {
                    "_provenance": "frozen from the 2026-07-17 verified backfill; "
                    "the phase_02 gate compares the live registry to this snapshot",
                    "counts": registry,
                },
                indent=2,
            )
            + "\n"
        )

        case = conn.execute(
            """
            SELECT t.ticker, f.concept, f.period_start, f.period_end, f.value,
                   f.accession, f.knowledge_time, n.value, n.accession, n.knowledge_time
            FROM facts f
            JOIN facts n ON n.fact_id = f.superseded_by
            JOIN tickers t ON t.company_id = f.company_id
            WHERE t.ticker = 'JNJ'
              AND f.concept = 'RevenueFromContractWithCustomerExcludingAssessedTax'
              AND f.period_start = '2023-01-02' AND f.period_end = '2023-07-02'
            """
        ).fetchone()
        if case is None:
            sys.exit("JNJ/Kenvue supersession case not found — investigate before freezing")
        (FIXTURES / "supersession_confirmed.json").write_text(
            json.dumps(
                {
                    "_provenance": "gate 9's frozen case. Confirmed 2026-07-17 against the "
                    "filings: JNJ H1-2023 revenue as reported in the Q2-2023 10-Q vs the "
                    "Kenvue-recast comparative in the Q2-2024 10-Q (consumer health moved "
                    "to discontinued operations). [HUMAN]: countersign during spot-checks.",
                    "human_countersigned": False,
                    "ticker": case[0],
                    "concept": case[1],
                    "period_start": str(case[2]),
                    "period_end": str(case[3]),
                    "original": {"value": str(case[4]), "accession": case[5],
                                 "knowledge_time": case[6].isoformat()},
                    "superseding": {"value": str(case[7]), "accession": case[8],
                                    "knowledge_time": case[9].isoformat()},
                },
                indent=2,
            )
            + "\n"
        )

        checks = []
        for accession, sections in HAND_CHECKED.items():
            for section, prefix in sections.items():
                row = conn.execute(
                    "SELECT count(*), COALESCE(sum(length(text)), 0) FROM chunks"
                    " WHERE accession = %s AND section = %s",
                    (accession, section),
                ).fetchone()
                if row[0] == 0:
                    sys.exit(f"{accession} {section}: no chunks — chunk pass incomplete")
                checks.append(
                    {
                        "accession": accession,
                        "section": section,
                        "min_chunks": max(1, row[0] // 2),
                        "min_chars": int(row[1]) // 2,
                        "opening_prefix": prefix,
                    }
                )
        (FIXTURES / "narrative_checks.json").write_text(
            json.dumps(
                {
                    "_provenance": "boundaries hand-checked 2026-07-17 on AAPL/MSFT/NVDA "
                    "latest 10-Ks; thresholds are half the observed sizes (drift alarms, "
                    "not exact pins — reruns may chunk slightly differently)",
                    "checks": checks,
                },
                indent=2,
            )
            + "\n"
        )
    print("frozen: registry_expected, supersession_confirmed, narrative_checks")


if __name__ == "__main__":
    main()
