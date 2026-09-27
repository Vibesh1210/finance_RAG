"""Section audit (I1): structural checks on one filing's extracted sections, catching the
three shapes the 2026-09 boundary bug took — overlap, a market-risk section larger than
the MD&A, and a section that starts with a table of contents. Pure; no DB."""

from __future__ import annotations

from us_rag.ingest.section_audit import audit_sections

PROSE = "This paragraph is long enough to count as real prose for the audit rules. " * 4


def para(tag: str) -> str:
    return f"{tag}: {PROSE}"


def test_clean_filing_has_no_problems():
    sections = {
        "Item 1A": [para(f"risk {i}") for i in range(30)],
        "Item 7": [para(f"mdna {i}") for i in range(30)],
        "Item 7A": [para("rates"), para("currency")],
    }
    assert audit_sections(sections) == []


def test_overlapping_sections_are_flagged():
    # DE shape: Item 7 and Item 7A both ran to the end of the document
    shared = [para(f"statements {i}") for i in range(40)]
    problems = audit_sections({"Item 7": [para("mdna")] + shared, "Item 7A": [para("mr")] + shared})
    assert any("overlap" in p for p in problems)


def test_short_repeated_footers_are_not_overlap():
    footer = "DEERE & COMPANY"
    sections = {
        "Item 1A": [para("risk 1"), footer, para("risk 2"), footer],
        "Item 7": [para("mdna 1"), footer, para("mdna 2"), footer],
    }
    assert audit_sections(sections) == []


def test_market_risk_larger_than_mdna_is_flagged():
    # JPM shape: "Item 7A" held the back half of the MD&A
    problems = audit_sections({
        "Item 7": [para(f"mdna {i}") for i in range(10)],
        "Item 7A": [para(f"mr {i}") for i in range(40)],
    })
    assert any("Item 7A" in p and "larger" in p for p in problems)
    q = audit_sections({
        "Part I Item 2 (MD&A)": [para("mdna")],
        "Part I Item 3": [para(f"mr {i}") for i in range(5)],
    })
    assert any("Part I Item 3" in p for p in q)


def test_section_starting_with_contents_is_flagged():
    # XOM shape: the MD&A began with "Forward-Looking Statements | 36 | Overview | 37 …"
    problems = audit_sections({
        "Item 7": ["Forward-Looking Statements", "36", "Overview", "37", "Business Environment",
                   "38"] + [para(f"mdna {i}") for i in range(20)],
    })
    assert any("contents" in p for p in problems)
