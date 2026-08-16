"""Narrative extraction (plan 2c): iXBRL HTML → sections → chunks → indexes.

Pipeline per corpus document:
1. Linearize the filer's HTML into text blocks (lxml), dropping the invisible
   iXBRL header, styles/scripts and display:none containers.
2. Find section boundaries from Item headings (design §3.3): 10-K Items 1 / 1A /
   7 / 7A; the 10-Q parallels (Part I Item 2 = MD&A, Part I Item 3, Part II
   Item 1A); EX-99.* exhibit bodies whole. Heading detection is heuristic and
   therefore GATE-CHECKED against hand-verified boundaries on real filings.
3. Chunk heading-aware: pack paragraphs to ≤ ~800 tokens with ~100-token carry-over,
   NEVER crossing a section boundary (a chunk mixing Risk Factors with MD&A
   poisons retrieval).
4. Index: text + tsvector (generated column) now; bge-m3 dense vectors via
   embed_missing() — a separate pass so extraction stays model-free and testable.

chunks.knowledge_time is inherited from the accession — narrative obeys the same
as-of physics as numbers.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
from lxml import html as lhtml

from us_rag.db import connect
from us_rag.env import repo_root
from us_rag.ingest.backfill import load_cached_submissions

TARGET_TOKENS = 800
OVERLAP_TOKENS = 100

# 10-K: section → the Item headings that terminate it (design §3.3)
TENK_SECTIONS = {
    "Item 1": {"1A"},
    "Item 1A": {"1B", "1C", "2"},
    "Item 7": {"7A"},
    "Item 7A": {"8"},
}
# 10-Q parallels; (part, item) keyed
TENQ_SECTIONS = {
    ("I", "2"): ("Part I Item 2 (MD&A)", {("I", "3"), ("I", "4")}),
    ("I", "3"): ("Part I Item 3", {("I", "4")}),
    ("II", "1A"): ("Part II Item 1A (Risk Factors)", {("II", "2"), ("II", "3"), ("II", "5"), ("II", "6")}),
}


@dataclass(frozen=True)
class Block:
    text: str
    in_table: bool
    linkish: bool  # mostly anchor text — a TOC row, not a heading


@dataclass(frozen=True)
class Heading:
    index: int  # position in the block list
    part: str | None  # 'I' | 'II' | None (10-K headings are partless here)
    item: str  # '1A', '7', ...


_ITEM_RE = re.compile(r"^\s*item\s+(\d{1,2}[a-c]?)\s*[.:—–-]?\s*(.{0,200})$", re.IGNORECASE)
_PART_RE = re.compile(r"^\s*part\s+(i{1,3}|iv)\b(\s*[.:—–-]\s*.{0,60})?$", re.IGNORECASE)
_PAGENUM_TAIL = re.compile(r"\d+\s*$")  # 'Item 1A. Risk Factors  12' → a TOC line

_DROP_TAGS = {"script", "style", "ix:header"}
_BLOCK_TAGS = {"p", "div", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"}


def blocks_from_html(raw: bytes | str) -> list[Block]:
    """Innermost block-level elements in document order, as normalized text."""
    tree = lhtml.fromstring(raw if isinstance(raw, bytes) else raw.encode())
    for element in tree.iter():
        tag = str(element.tag).lower() if isinstance(element.tag, str) else ""
        style = (element.get("style") or "").replace(" ", "").lower()
        if tag in _DROP_TAGS or "display:none" in style:
            element.drop_tree()
    blocks: list[Block] = []
    for element in tree.iter():
        tag = str(element.tag).lower() if isinstance(element.tag, str) else ""
        if tag not in _BLOCK_TAGS:
            continue
        if any(
            str(child.tag).lower() in _BLOCK_TAGS
            for child in element.iterdescendants()
            if isinstance(child.tag, str)
        ):
            continue  # not innermost — its children will be emitted instead
        text = re.sub(r"\s+", " ", element.text_content()).strip()
        if not text:
            continue
        link_len = sum(len(a.text_content()) for a in element.iterdescendants("a"))
        blocks.append(
            Block(
                text=text,
                in_table=any(
                    str(ancestor.tag).lower() == "table" for ancestor in element.iterancestors()
                ),
                linkish=link_len >= max(1, len(text)) * 0.8,
            )
        )
    return blocks


def find_headings(blocks: list[Block], *, default_part: str | None = None) -> list[Heading]:
    """Item-heading CANDIDATES: short standalone blocks, not TOC links, no trailing
    page number. Tables are allowed — WMT/XOM/DE set real headings inside layout
    tables — so TOC rows also land here; the body-quality rule in _accept() is
    what separates a heading from a TOC row. Part context tracked as we go; a
    10-Q starts in Part I by definition (default_part='I')."""
    headings: list[Heading] = []
    part: str | None = default_part
    for index, block in enumerate(blocks):
        if block.linkish:
            continue
        if part_match := _PART_RE.match(block.text):
            part = part_match.group(1).upper()
            continue
        item_match = _ITEM_RE.match(block.text)
        if not item_match:
            continue
        title = item_match.group(2)
        if _PAGENUM_TAIL.search(title):
            continue
        headings.append(Heading(index=index, part=part, item=item_match.group(1).upper()))
    return headings


def _accept(body: list[Block], floor: int) -> bool:
    """A real section, not a TOC hit or a cross-reference stub: enough total text
    AND at least one substantial prose paragraph outside any table. TOC rows are
    all-table by construction; 'incorporated by reference' stubs are tiny."""
    total = sum(len(b.text) for b in body)
    has_prose = any(
        len(b.text) >= 200 and not b.in_table and not b.linkish for b in body
    )
    return total >= floor and has_prose


# P-US-2 pivot (triggered 2026-07-17: JPM/DE/XOM cross-reference Items 7/7A to a
# caption elsewhere in the same document): when the Item-heading pass finds no
# body, locate the section by its CAPTION instead.
_MDNA_CAPTION = re.compile(
    r"^(management[’']?s discussion and analysis\b.{0,140}"
    r"|the following is management[’']?s discussion and analysis\b.{0,200})$",
    re.IGNORECASE,
)
_MARKET_RISK_CAPTION = re.compile(
    r"^(quantitative and qualitative disclosures about market risk\b.{0,60}"
    r"|market risk)$",
    re.IGNORECASE,
)
_STATEMENTS_CAPTION = re.compile(
    r"^(financial statements and supplementary data"
    r"|index to (the )?financial statements.{0,40}"
    r"|report of independent registered public accounting firm.{0,40}"
    r"|consolidated statements? of (income|operations|earnings)\b.{0,60})$",
    re.IGNORECASE,
)


def _caption_section(
    blocks: list[Block], start: re.Pattern, ends: list[re.Pattern], floor: int
) -> list[str] | None:
    def is_caption(block: Block, pattern: re.Pattern) -> bool:
        return not block.linkish and len(block.text) <= 260 and bool(pattern.match(block.text))

    for index, block in enumerate(blocks):
        if not is_caption(block, start):
            continue
        end_index = next(
            (
                j
                for j in range(index + 1, len(blocks))
                if any(is_caption(blocks[j], p) for p in ends)
            ),
            len(blocks),
        )
        body = blocks[index + 1 : end_index]
        if _accept(body, floor):
            return [b.text for b in body]
    return None


def extract_10k_sections(blocks: list[Block]) -> dict[str, list[str]]:
    headings = find_headings(blocks)
    sections: dict[str, list[str]] = {}
    for label, terminators in TENK_SECTIONS.items():
        wanted = label.split()[1].upper()
        for position, heading in enumerate(headings):
            if heading.item != wanted:
                continue
            end_index = next(
                (h.index for h in headings[position + 1 :] if h.item in terminators),
                len(blocks),
            )
            body = blocks[heading.index + 1 : end_index]
            if _accept(body, 500):
                sections[label] = [b.text for b in body]
                break
    if "Item 7" not in sections:
        body = _caption_section(
            blocks, _MDNA_CAPTION, [_MARKET_RISK_CAPTION, _STATEMENTS_CAPTION], 500
        )
        if body:
            sections["Item 7"] = body
    if "Item 7A" not in sections:
        body = _caption_section(blocks, _MARKET_RISK_CAPTION, [_STATEMENTS_CAPTION], 500)
        if body:
            sections["Item 7A"] = body
    return sections


def extract_10q_sections(blocks: list[Block]) -> dict[str, list[str]]:
    headings = find_headings(blocks, default_part="I")
    sections: dict[str, list[str]] = {}
    for (part, item), (label, terminators) in TENQ_SECTIONS.items():
        for position, heading in enumerate(headings):
            if (heading.part, heading.item) != (part, item):
                continue
            end_index = next(
                (h.index for h in headings[position + 1 :] if (h.part, h.item) in terminators),
                len(blocks),
            )
            body = blocks[heading.index + 1 : end_index]
            if _accept(body, 200):  # 10-Q risk-factor items can be short
                sections[label] = [b.text for b in body]
                break
    if "Part I Item 2 (MD&A)" not in sections:  # P-US-2: JPM cross-references it
        body = _caption_section(
            blocks, _MDNA_CAPTION, [_MARKET_RISK_CAPTION, _STATEMENTS_CAPTION], 500
        )
        if body:
            sections["Part I Item 2 (MD&A)"] = body
    return sections


def extract_exhibit(blocks: list[Block]) -> list[str]:
    """EX-99 bodies are taken whole (P-US-3 allows single-chunk storage)."""
    return [b.text for b in blocks]


# ---------- chunking ----------


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)  # ~4 chars/token for English; a budget, not truth


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def chunk_paragraphs(paragraphs: list[str]) -> list[str]:
    """Greedy packing to ≤ TARGET_TOKENS with ~OVERLAP_TOKENS carried over between
    consecutive chunks. Paragraph boundaries are respected; an oversized single
    paragraph falls back to sentence packing."""
    pieces: list[str] = []
    for paragraph in paragraphs:
        if approx_tokens(paragraph) > TARGET_TOKENS:
            pieces.extend(_SENTENCE_RE.split(paragraph))
        else:
            pieces.append(paragraph)

    chunks: list[str] = []
    current: list[str] = []
    budget = 0
    for piece in pieces:
        cost = approx_tokens(piece)
        if current and budget + cost > TARGET_TOKENS:
            chunks.append("\n".join(current))
            overlap: list[str] = []
            spent = 0
            for prior in reversed(current):
                spent += approx_tokens(prior)
                overlap.insert(0, prior)
                if spent >= OVERLAP_TOKENS:
                    break
            current, budget = overlap, sum(approx_tokens(p) for p in overlap)
        current.append(piece)
        budget += cost
    if current:
        chunks.append("\n".join(current))
    return [c for c in chunks if c.strip()]


# ---------- pipeline ----------


def _fiscal_context(conn: psycopg.Connection, company_id: int, form: str, report_date) -> str | None:
    if report_date is None:
        return None
    prefer_fy = form.startswith("10-K")
    row = conn.execute(
        "SELECT fiscal_year, fiscal_period FROM fiscal_calendars"
        " WHERE company_id = %s AND period_end = %s"
        " ORDER BY (fiscal_period = 'FY') " + ("DESC" if prefer_fy else "ASC") + " LIMIT 1",
        (company_id, report_date),
    ).fetchone()
    if row is None:
        return None
    year, period = row
    return f"FY{year}" if period == "FY" else f"FY{year} {period}"


def sections_for_document(form: str, folder: Path, primary_blob: Path) -> dict[str, list[str]]:
    """section label → paragraphs, for one corpus document."""
    if form.startswith("10-K"):
        return extract_10k_sections(blocks_from_html(primary_blob.read_bytes()))
    if form.startswith("10-Q"):
        return extract_10q_sections(blocks_from_html(primary_blob.read_bytes()))
    # 8-K: chunk the EX-99.* exhibits, never the boilerplate 8-K body
    manifest_path = folder / "_manifest.json"
    if not manifest_path.exists():
        return {}
    sections: dict[str, list[str]] = {}
    for name, exhibit_type in json.loads(manifest_path.read_text())["exhibits"].items():
        path = folder / name
        if path.exists():
            body = extract_exhibit(blocks_from_html(path.read_bytes()))
            if body:
                sections[exhibit_type] = body
    return sections


def chunk_company(conn: psycopg.Connection, ticker: str) -> dict:
    company_id, cik = conn.execute(
        "SELECT company_id, cik FROM companies JOIN tickers USING (company_id)"
        " WHERE ticker = %s",
        (ticker,),
    ).fetchone()
    report_dates = {f.accession: f.report_date for f in load_cached_submissions(cik)}
    already = {
        row[0] for row in conn.execute("SELECT DISTINCT accession FROM chunks", ())
    }
    documents = conn.execute(
        "SELECT accession, form, acceptance_datetime, blob_path FROM documents"
        " WHERE company_id = %s AND corpus AND status = 'fetched'"
        " ORDER BY acceptance_datetime",
        (company_id,),
    ).fetchall()
    summary = {"ticker": ticker, "documents": 0, "chunks": 0, "empty_10x": []}
    for accession, form, acceptance, blob_path in documents:
        if accession in already:
            continue
        primary = repo_root() / blob_path
        sections = sections_for_document(form, primary.parent, primary)
        if not sections and form.startswith(("10-K", "10-Q")):
            summary["empty_10x"].append(accession)  # surfaced, not swallowed
        fiscal = _fiscal_context(conn, company_id, form, report_dates.get(accession))
        count = 0
        for section, paragraphs in sections.items():
            for text in chunk_paragraphs(paragraphs):
                conn.execute(
                    "INSERT INTO chunks (accession, company_id, doc_type, section,"
                    " fiscal_context, knowledge_time, text)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (accession, company_id, form, section, fiscal, acceptance, text),
                )
                count += 1
        summary["documents"] += 1
        summary["chunks"] += count
    conn.commit()
    return summary


def embed_missing(conn: psycopg.Connection, *, batch_size: int = 8) -> int:
    """Dense bge-m3 vectors for chunks that lack one. Separate pass: the extractor
    stays model-free; this needs the 'embed' dependency group (U9).

    Memory-bounded for 8 GB Apple-Silicon laptops (DECISIONS.md #11). Defaults:
    CPU device — the earlier default ran the model on the M-series GPU, which
    shares the 8 GB with the display and OOM'd mid-run; a small batch; and a
    2048-token sequence cap (the longest real chunk is 1634 tokens, so no chunk
    is ever shortened — verified across the corpus). Override via US_RAG_EMBED_DEVICE
    (e.g. 'mps' for speed) / US_RAG_EMBED_BATCH / US_RAG_EMBED_MAXLEN."""
    import os

    from sentence_transformers import SentenceTransformer  # heavy import, on purpose here

    device = os.environ.get("US_RAG_EMBED_DEVICE", "cpu")
    batch_size = int(os.environ.get("US_RAG_EMBED_BATCH", str(batch_size)))
    max_len = int(os.environ.get("US_RAG_EMBED_MAXLEN", "2048"))
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    model.max_seq_length = max_len
    done = 0
    while True:
        rows = conn.execute(
            "SELECT chunk_id, text FROM chunks WHERE embedding IS NULL"
            " ORDER BY chunk_id LIMIT %s",
            (batch_size,),
        ).fetchall()
        if not rows:
            return done
        vectors = model.encode(
            [text for _, text in rows],
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        for (chunk_id, _), vector in zip(rows, vectors):
            literal = "[" + ",".join(f"{v:.7f}" for v in vector) + "]"
            conn.execute(
                "UPDATE chunks SET embedding = %s::vector WHERE chunk_id = %s",
                (literal, chunk_id),
            )
        conn.commit()
        done += len(rows)
        print(f"embedded {done} chunks", flush=True)


def main(tickers: list[str] | None = None, *, embed: bool = False) -> None:
    universe = [
        entry["ticker"] for entry in json.loads((repo_root() / "universe.json").read_text())
    ]
    with connect() as conn:
        for ticker in tickers or universe:
            print(json.dumps(chunk_company(conn, ticker)))
        if embed:
            print(f"embedding pass: {embed_missing(conn)} chunks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract, chunk and index narrative text")
    parser.add_argument("--tickers", nargs="*")
    parser.add_argument("--embed", action="store_true", help="also run the embedding pass")
    args = parser.parse_args()
    main(args.tickers, embed=args.embed)
