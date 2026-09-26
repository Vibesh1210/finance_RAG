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
