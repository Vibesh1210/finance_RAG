"""Narrative extraction + chunking tests (plan 2c), fixtures-only. Live-filing
boundary quality is the gate's hand-checked concern; these test the machinery."""

from __future__ import annotations

from us_rag.ingest.narrative import (
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    approx_tokens,
    blocks_from_html,
    chunk_paragraphs,
    extract_10k_sections,
    extract_10q_sections,
)

MINI_10K = """
<html><body>
<ix:header><div>hidden xbrl junk that must never surface</div></ix:header>
<div style="display:none">also hidden</div>
<table>
  <tr><td><a href="#i1">Item 1</a></td><td><a href="#i1">Business</a></td><td>3</td></tr>
  <tr><td><a href="#i1a">Item 1A</a></td><td><a href="#i1a">Risk Factors</a></td><td>9</td></tr>
</table>
<div>PART I</div>
<div>Item 1. Business</div>
<p>%s</p>
<div>Item 1A. Risk Factors</div>
<p>%s</p>
<div>Item 1B. Unresolved Staff Comments</div>
<p>None.</p>
<div>Item 7. Management&#8217;s Discussion and Analysis of Financial Condition and Results of Operations</div>
<p>%s</p>
<div>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</div>
<p>%s</p>
<div>Item 8. Financial Statements and Supplementary Data</div>
<p>statements here</p>
</body></html>
""" % (
    "We design products. " * 40,
    "Our business faces many risks that could hurt us badly. " * 40,
    "Revenue went up because customers bought more things this year. " * 40,
    "We are exposed to interest rate risk in our portfolio holdings. " * 40,
)


def test_extract_10k_sections_boundaries_and_hidden_content():
    sections = extract_10k_sections(blocks_from_html(MINI_10K))
    assert set(sections) == {"Item 1", "Item 1A", "Item 7", "Item 7A"}
    assert "products" in sections["Item 1"][0]
    assert all("hidden" not in p for paras in sections.values() for p in paras)
    # boundaries: risk text only in 1A, MD&A text only in 7
    assert not any("risks" in p for p in sections["Item 1"])
    assert not any("Revenue went up" in p for p in sections["Item 1A"])


MINI_10Q = """
<html><body>
<div>PART I &#8212; FINANCIAL INFORMATION</div>
<div>Item 1. Financial Statements</div>
<p>tables of numbers</p>
<div>Item 2. Management&#8217;s Discussion and Analysis of Financial Condition and Results of Operations</div>
<p>%s</p>
<div>Item 3. Quantitative and Qualitative Disclosures About Market Risk</div>
<p>%s</p>
<div>Item 4. Controls and Procedures</div>
<p>controls fine</p>
<div>PART II &#8212; OTHER INFORMATION</div>
<div>Item 1A. Risk Factors</div>
<p>%s</p>
<div>Item 2. Unregistered Sales of Equity Securities and Use of Proceeds</div>
<p>buybacks</p>
</body></html>
""" % (
    "The quarter was good and margins expanded across our segments. " * 20,
    "Rates moved and we hedged accordingly with various instruments. " * 10,
    "There were no material changes from the risk factors previously disclosed except this one. " * 5,
)


def test_extract_10q_sections_tracks_parts():
    sections = extract_10q_sections(blocks_from_html(MINI_10Q))
    assert "Part I Item 2 (MD&A)" in sections
    assert "Part II Item 1A (Risk Factors)" in sections
    assert any("margins expanded" in p for p in sections["Part I Item 2 (MD&A)"])
    assert not any("buybacks" in p for p in sections["Part II Item 1A (Risk Factors)"])


def test_chunks_respect_budget_and_overlap():
    paragraphs = [f"Paragraph {i}. " + ("Filler sentence with words. " * 20) for i in range(40)]
    chunks = chunk_paragraphs(paragraphs)
    assert len(chunks) > 1
    for chunk in chunks:
        # budget: target plus one paragraph of slack (a paragraph is never split
        # unless it alone exceeds the target)
        assert approx_tokens(chunk) <= TARGET_TOKENS + 160
    # consecutive chunks share overlap: the head of chunk N+1 appears in chunk N
    for first, second in zip(chunks, chunks[1:]):
        head = second.split("\n")[0]
        assert head in first
    # nothing lost: every paragraph appears somewhere
    joined = "\n".join(chunks)
    assert all(f"Paragraph {i}." in joined for i in range(40))


def test_oversized_paragraph_falls_back_to_sentences():
    monster = "This is one sentence of a monster paragraph. " * 200  # ~2300 tokens
    chunks = chunk_paragraphs([monster])
    assert len(chunks) >= 3
    assert all(approx_tokens(c) <= TARGET_TOKENS + 160 for c in chunks)


def test_overlap_is_bounded():
    paragraphs = ["Short para. " + "x " * 50 for _ in range(60)]
    chunks = chunk_paragraphs(paragraphs)
    for first, second in zip(chunks, chunks[1:]):
        shared = set(first.split("\n")) & set(second.split("\n"))
        assert approx_tokens("\n".join(shared)) <= OVERLAP_TOKENS + 160


# ---- caption fallback (P-US-2 filers: Items 7/7A are cross-references) — I1 regressions ----

# JPM shape (FY2025 10-K): a contents table lists "Management's discussion and analysis:"
# followed by linked entries, and a risk index lists "Market Risk | 133-142". Neither is a
# section. The real MD&A starts at a standalone caption and runs to the auditor's report;
# JPM's market-risk discussion is a subsection INSIDE it, so there is no separate Item 7A.
MINI_JPM_10K = """
<html><body>
<div>Item 7. Management&#8217;s Discussion and Analysis</div><p>See pages 46-161.</p>
<div>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</div><p>See pages 133-142.</p>
<div>Item 8. Financial Statements and Supplementary Data</div><p>See page 162.</p>
<table>
  <tr><td>Management&#8217;s discussion and analysis:</td></tr>
  <tr><td><a href="#intro">Introduction</a></td><td>46</td></tr>
  <tr><td><a href="#exec">Executive Overview</a></td><td>47</td></tr>
</table>
<div>Management&#8217;s discussion and analysis</div>
<p>%s</p>
<table>
  <tr><td>Market Risk</td><td>133-142</td></tr>
  <tr><td>Country Risk</td><td>143-144</td></tr>
</table>
<div>MARKET RISK MANAGEMENT</div>
<p>%s</p>
<div>Report of Independent Registered Public Accounting Firm</div>
<p>%s</p>
</body></html>
""" % (
    "The following is Management's discussion of the Firm's results this year. " * 30,
    "Market risk is the risk of loss from changes in market prices and rates. " * 30,
    "In our opinion the consolidated financial statements present fairly. " * 30,
)


def test_caption_fallback_skips_contents_and_index_rows_jpm_shape():
    sections = extract_10k_sections(blocks_from_html(MINI_JPM_10K))
    mdna = sections["Item 7"]
    assert "discussion of the Firm's results" in mdna[0]         # starts at the real caption,
    assert not any(p in ("Introduction", "46") for p in mdna)    # not in the contents table
    assert any("Market risk is the risk of loss" in p for p in mdna)  # subsection stays in MD&A
    assert not any("present fairly" in p for p in mdna)          # stops at the auditor's report
    assert "Item 7A" not in sections                             # an index row is not a section


# DE shape (FY2025 10-K): the Part II item list is a layout table ("ITEM 7A." | caption),
# and Item 7A's only text is one short inline paragraph before "ITEM 8." — below the section
# floor, so it is not a section; the market-risk discussion lives inside the MD&A proper,
# which sits later and is followed by statements captioned "STATEMENTS OF CONSOLIDATED
# INCOME" (the item list also has "…SUPPLEMENTARY DATA." with a trailing period).
MINI_DE_10K = """
<html><body>
<table><tr><td>ITEM 7.</td><td>MANAGEMENT&#8217;S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS.</td></tr></table>
<p>See the information under the caption Management&#8217;s Discussion and Analysis.</p>
<table><tr><td>ITEM 7A.</td><td>QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK.</td></tr></table>
<p>%s</p>
<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA.</td></tr></table>
<p>See the Consolidated Financial Statements and notes thereto that follow.</p>
<div>MANAGEMENT&#8217;S DISCUSSION AND ANALYSIS</div>
<p>%s</p>
<div>STATEMENTS OF CONSOLIDATED INCOME</div>
<p>%s</p>
</body></html>
""" % (
    "We are exposed to a variety of market risks, including interest rates and currency. " * 3,
    "Net sales and revenues increased this year on higher shipment volumes. " * 30,
    "Net sales 45,684 cost of sales 30,000 selling expenses 5,000 and other lines. " * 30,
)


def test_caption_fallback_stops_at_item_heading_and_de_statement_captions():
    sections = extract_10k_sections(blocks_from_html(MINI_DE_10K))
    assert "Item 7A" not in sections           # a short inline stub before "ITEM 8." is not a section
    mdna = sections["Item 7"]
    assert any("higher shipment volumes" in p for p in mdna)
    assert not any("cost of sales 30,000" in p for p in mdna)     # ends at STATEMENTS OF CONSOLIDATED INCOME


# XOM shape (FY2024 10-K): the Financial Section opens with a contents table whose FIRST
# row is the MD&A title, then entries with page numbers, group headings without one
# ("Consolidated Financial Statements"), and a "Report of Independent…| 74" row. The real
# MD&A caption comes later. The contents table must not become the MD&A.
MINI_XOM_10K = """
<html><body>
<div>Item 7. Management&#8217;s Discussion and Analysis</div><p>Reference is made to the Financial Section.</p>
<div>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</div><p>Reference is made to the Financial Section.</p>
<div>Item 8. Financial Statements and Supplementary Data</div><p>Reference is made to the Financial Section.</p>
<table>
  <tr><td>Management&#8217;s Discussion and Analysis of Financial Condition and Results of Operations</td></tr>
  <tr><td>Forward-Looking Statements</td><td><a href="#fls">39</a></td></tr>
  <tr><td>Overview</td><td><a href="#ov">40</a></td></tr>
  <tr><td>Report of Independent Registered Public Accounting Firm</td><td><a href="#rep">74</a></td></tr>
  <tr><td>Consolidated Financial Statements</td></tr>
  <tr><td>Statement of Income</td><td><a href="#inc">77</a></td></tr>
</table>
<div>MANAGEMENT&#8217;S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS</div>
<div>FORWARD-LOOKING STATEMENTS</div>
<p>%s</p>
<div>Report of Independent Registered Public Accounting Firm</div>
<p>%s</p>
</body></html>
""" % (
    "Statements related to future events and projections are forward-looking statements. " * 20,
    "In our opinion the consolidated financial statements present fairly. " * 20,
)


def test_caption_section_skips_a_contents_table_titled_like_the_section_xom_shape():
    mdna = extract_10k_sections(blocks_from_html(MINI_XOM_10K))["Item 7"]
    assert mdna[0] == "FORWARD-LOOKING STATEMENTS"               # real text starts here
    assert not any(p in ("39", "40", "Overview", "Consolidated Financial Statements") for p in mdna)
    assert not any("present fairly" in p for p in mdna)
