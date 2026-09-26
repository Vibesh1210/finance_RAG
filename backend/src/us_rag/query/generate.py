"""Phase 5 answer pipeline (design §6.0/§6.4): route → fetch → generate → verify.

The full answer contract for M0:
- numbers come from the deterministic executor (Phase 4), never the LLM (no-LLM-arithmetic);
- every emitted number is verifier-checked (Phase 4 verifier) — mismatch → abstain;
- every number is cited `[accession · period · as-of]`;
- unanswerable classes get a typed refusal; ambiguous questions get a clarification;
- outputs are sourced decision-support, never advice (posture guard, §1.4).

Generation is LLM-injectable: `generate_fn` defaults to None (no external call — narrative
answers return a grounded, cited summary), so the M0 gate runs fixtures-only. Pass
`generate_fn=gemini_generate` in real use for prose synthesis over the retrieved passages.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import psycopg

from us_rag.entities import resolve_one
from us_rag.query.metrics import (
    Abstention,
    MetricResult,
    derived_margin,
    metric_compare,
    metric_value,
    q4_value,
)
from us_rag.query.retrieve import retrieve
from us_rag.query.router import route
from us_rag.query.verify import verify

POSTURE = "This is sourced information for decision support, not investment advice."

_METRIC_KEYS = [
    ("diluted earnings per share", "diluted_eps"), ("diluted eps", "diluted_eps"),
    ("earnings per share", "diluted_eps"), ("total net sales", "revenue"),
    ("net sales", "revenue"), ("total revenues", "revenue"), ("total revenue", "revenue"),
    ("gross margin", "gross_margin"), ("gross profit", "gross_profit"),
    ("cost of revenue", "cost_of_revenue"), ("net income", "net_income"),
    ("operating income", "operating_income"), ("total assets", "total_assets"),
    ("total liabilities", "total_liabilities"), ("stockholders equity", "stockholders_equity"),
    ("shareholders equity", "stockholders_equity"), ("operating cash flow", "operating_cash_flow"),
    ("capital expenditure", "capital_expenditure"), ("revenue", "revenue"), ("sales", "revenue"),
    ("eps", "diluted_eps"),
]


@dataclass
class Answer:
    status: str  # answered | abstained | refused | clarify
    route: str
    text: str
    citations: list[str] = field(default_factory=list)
    numbers: list = field(default_factory=list)  # verified executor results backing the answer
    reason: str | None = None


def extract_metric_key(question: str) -> str | None:
    q = question.lower()
    for keyword, key in _METRIC_KEYS:
        if keyword in q:
            return key
    return None


def extract_period(question: str) -> str | None:
    q = question.lower()
    if m := re.search(r"q([1-4])\s*fy\s*(\d{4})", q):
        return f"Q{m.group(1)} FY{m.group(2)}"
    if m := re.search(r"(first|second|third|fourth)[- ]quarter\s+(?:of\s+)?(\d{4})", q):
        n = {"first": 1, "second": 2, "third": 3, "fourth": 4}[m.group(1)]
        return f"Q{n} FY{m.group(2)}"
    if m := re.search(r"q([1-4])\s+(?:fy\s*)?(\d{4})", q):
        return f"Q{m.group(1)} FY{m.group(2)}"
    if m := re.search(r"\bfy\s*(\d{4})", q):
        return f"FY{m.group(1)}"
    if m := re.search(r"fiscal(?:\s+year)?\s+(?:ended\s+\w+\s+\d{1,2},?\s+)?(\d{4})", q):
        return f"FY{m.group(1)}"
    if m := re.search(r"ended\s+\w+\s+\d{1,2},?\s+(\d{4})", q):
        return f"FY{m.group(1)}"
    return None


def _as_reported(value: Decimal, unit: str) -> str:
    if unit and "shares" in unit:
        return f"${value} per share"
    return f"${Decimal(value) / Decimal(1_000_000):,.0f} million"


def _cite(res) -> str:
    c = res.citation
    return f"[{c.accession} · {c.period} · as-of {c.as_of}]"


def _company_ids(conn, tickers):
    return [resolve_one(conn, t).company_id for t in tickers] or None


def _metric_answer(conn, question, decision, as_of) -> Answer:
    mk = extract_metric_key(question)
    period = extract_period(question)
    if mk is None or period is None or not decision.tickers:
        return Answer("abstained", decision.route, "Couldn't pin down the metric, period, or company precisely.",
                      reason="unresolved metric/period/entity")

    if len(decision.tickers) >= 2:
        res = metric_compare(conn, decision.tickers, mk, period, as_of=as_of)
        parts, cites, backing = [], [], []
        for leg in res.results:
            if isinstance(leg, Abstention):
                parts.append(f"{leg.ticker}: no data")
                continue
            if not verify(leg, claimed_value=leg.value).ok:
                return Answer("abstained", decision.route, "A number failed verification.", reason="verify failed")
            parts.append(f"{leg.ticker} {_as_reported(leg.value, leg.unit)}")
            cites.append(_cite(leg))
            backing.append(leg)
        note = f" ({res.caveat})" if res.caveat else ""
        text = f"{mk.replace('_', ' ').title()} for {period} — " + "; ".join(parts) + note + f". {POSTURE}"
        return Answer("answered", decision.route, text, cites, backing, res.caveat)

    tk = decision.tickers[0]
    if mk == "gross_margin":
        res = derived_margin(conn, tk, period, as_of=as_of)
    elif period.startswith("Q4"):
        res = q4_value(conn, tk, mk, int(period[-4:]), as_of=as_of)
    else:
        res = metric_value(conn, tk, mk, period, as_of=as_of)

    if isinstance(res, Abstention):
        return Answer("abstained", decision.route, f"I can't provide that: {res.detail}.", reason=res.reason)
    if not verify(res, claimed_value=res.value).ok:
        return Answer("abstained", decision.route, "A number failed verification; withholding it.", reason="verify failed")

    cite = _cite(res) if getattr(res, "citation", None) else ""
    caveat = f" ({res.caveat})" if getattr(res, "caveat", None) else ""
    label = mk.replace("_", " ")
    text = f"{tk}'s {label} for {period} was {_as_reported(res.value, getattr(res, 'unit', 'USD'))}{caveat} {cite}. {POSTURE}"
    return Answer("answered", decision.route, text, [cite] if cite else [], [res], getattr(res, "caveat", None))


def _narrative_answer(conn, question, decision, as_of, generate_fn) -> Answer:
    hits = retrieve(conn, question, as_of=as_of, top_k=8, company_ids=_company_ids(conn, decision.tickers))
    if not hits:
        return Answer("abstained", decision.route, "No relevant passages were found as of that date.",
                      reason="no retrieval hits")
    citations = [f"[{h.accession} · {h.section}]" for h in hits[:3]]
    if generate_fn is None:  # fixtures-only default: grounded, cited summary without an LLM call
        srcs = ", ".join(f"{h.section} of {h.accession}" for h in hits[:3])
        text = f"Relevant disclosure is in {srcs} (as of {as_of}). {POSTURE}"
    else:
        evidence = [{"accession": h.accession, "section": h.section, "text": h.text} for h in hits[:6]]
        text = f"{generate_fn(question, evidence).strip()} {POSTURE}"
    return Answer("answered", decision.route, text, citations)


def answer(
    conn: psycopg.Connection, question: str, *, as_of: date | datetime,
    generate_fn: Callable[[str, list], str] | None = None,
) -> Answer:
    """Route the question and produce a verified, cited answer — or a typed refusal /
    clarification. `as_of` is required (every answer is point-in-time)."""
    decision = route(conn, question)
    if decision.route in ("unanswerable", "graph"):
        return Answer("refused", decision.route, f"I can't answer that — {decision.reason}.", reason=decision.reason)
    if decision.route == "clarify":
        return Answer("clarify", decision.route, f"That's ambiguous: {decision.reason}. Could you specify?",
                      reason=decision.reason)
    if decision.route == "metric":
        return _metric_answer(conn, question, decision, as_of)
    return _narrative_answer(conn, question, decision, as_of, generate_fn)


def gemini_generate(question: str, evidence: list[dict]) -> str:
    """Real narrative synthesis over retrieved passages (Gemini, ADR-0008). Opt-in —
    never called by the fixtures-only gate. Instructed to cite and to invent no numbers."""
    from google import genai

    client = genai.Client()
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    passages = "\n\n".join(f"[{e['accession']} · {e['section']}]\n{e['text'][:1500]}" for e in evidence)
    prompt = (
        "Answer the question using ONLY the passages below. Cite the [accession · section] you "
        "used. If the passages do not answer it, say so plainly. Do NOT state any number that is "
        f"not present verbatim in a passage.\n\nQuestion: {question}\n\nPassages:\n{passages}"
    )
    return client.models.generate_content(model=model, contents=prompt).text
