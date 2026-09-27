"""Section audit (I1, 2026-09-27): structural checks on one filing's extracted sections.

Section boundaries come from heading heuristics, which unusual layouts can fool. Hand-
checking a few filings (gate 2, check 4) missed JPM's and DE's runaway sections, so this
audits EVERY filing for the shapes that bug took:

1. overlap      — two sections share real paragraphs (DE: Item 7 and 7A both ran to the end)
2. inverted     — the market-risk section is larger than the MD&A it belongs beside
                  (JPM: "Item 7A" held the back half of the MD&A)
3. contents     — a section opens with a table of contents (XOM: "Overview | 37 | …")

Size alone is NOT a rule: JPM's MD&A is legitimately long, and MSFT/NVDA repeat full risk
factors in every 10-Q. Pure function over {section label: paragraphs}; no DB.
"""

from __future__ import annotations

import re
from itertools import combinations

# paragraphs shorter than this (page footers, "DEERE & COMPANY", page numbers) are ignored
# for overlap — they legitimately repeat across sections
MIN_PROSE = 200
OVERLAP_SHARE = 0.2  # flag when >20% of the smaller section's prose also appears in another
CONTENTS_WINDOW = 6  # a section's first N paragraphs …
CONTENTS_PAGE_REFS = 2  # … may hold at most 1 page reference

_PAGE_REF = re.compile(r"^\(?\d{1,3}(\s*[-–]\s*\d{1,3})?\)?$")

# (market-risk section, the MD&A it must not outgrow)
_MARKET_RISK_PAIRS = (
    ("Item 7A", "Item 7"),
    ("Part I Item 3", "Part I Item 2 (MD&A)"),
)


def _prose(paragraphs: list[str]) -> set[str]:
    return {p for p in paragraphs if len(p) >= MIN_PROSE}


def audit_sections(sections: dict[str, list[str]]) -> list[str]:
    """Problems found in one filing's sections; an empty list means it looks sound."""
    problems: list[str] = []

    for (a, pa), (b, pb) in combinations(sections.items(), 2):
        sa, sb = _prose(pa), _prose(pb)
        if not sa or not sb:
            continue
        shared = len(sa & sb) / min(len(sa), len(sb))
        if shared > OVERLAP_SHARE:
            problems.append(f"overlap: {a} and {b} share {shared:.0%} of their prose")

    size = {label: sum(map(len, paras)) for label, paras in sections.items()}
    for market_risk, mdna in _MARKET_RISK_PAIRS:
        if market_risk in size and mdna in size and size[market_risk] > size[mdna]:
            problems.append(
                f"inverted: {market_risk} ({size[market_risk]:,} chars) is larger than "
                f"{mdna} ({size[mdna]:,} chars)"
            )

    for label, paragraphs in sections.items():
        refs = sum(1 for p in paragraphs[:CONTENTS_WINDOW] if _PAGE_REF.match(p.strip()))
        if refs >= CONTENTS_PAGE_REFS:
            problems.append(f"contents: {label} opens with a table of contents ({refs} page refs)")

    return problems
