"""Phase 5 router (design §6.0): map a question to a typed route.

Deterministic for M0 (ADR-0014) — auditable, testable, and it cannot commit the one
dangerous misroute (a numeric question going to the text-only path). Entity resolution and
fiscal resolution run BEFORE routing; the router never guesses a period. An LLM classifier
is the drop-in upgrade behind the same `RouteDecision` interface.

Routes: metric (SQL) · narrative (retrieval) · graph (M2+) · unanswerable · clarify · hybrid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import psycopg

ROUTES = {"metric", "narrative", "graph", "unanswerable", "clarify", "hybrid"}

# companies outside the 10-name universe that show up in questions -> out of coverage
OUT_OF_UNIVERSE = {
    "tesla", "chevron", "amd", "google", "alphabet", "amazon", "meta", "ford",
    "intel", "oracle", "tsmc", "samsung", "berkshire", "pfizer", "boeing",
}
COUNTRIES = {
    "germany", "china", "europe", "india", "japan", "france", "canada",
    "mexico", "brazil", "britain", "italy", "spain",
}

_METRIC = r"revenue|net sales|sales|net income|income|earnings|eps|margin|assets|liabilities|equity|cash flow|capex|capital expenditure|profit|book value|how much"
_NARRATIVE = r"risk|disclose|discuss|describe|management (say|said|discussion)|commentary|factors|md&a|outlook|strategy|competition|account(ed|ing) for|what did .* (say|disclose|describe|discuss)|how did .* (say|describe|account|affect|change|compare)"
_SEGMENT = r"segment|membership fee|data center|intelligent cloud|services revenue|products revenue|construction industries|consumer & community|precision ag"
_GRAPH = r"which of .*suppliers|suppliers? also|exposed to|same .*(supplier|vendor)|concentration among|customers of|trace the .*relationship|relationship between .* and"


@dataclass
class RouteDecision:
    route: str
    confidence: float
    tickers: list[str] = field(default_factory=list)
    reason: str = ""


def _entity_scanners(conn: psycopg.Connection):
    names: list[tuple[str, str]] = []  # (lowercased alias, ticker)
    for tk, alias in conn.execute(
        "SELECT t.ticker, a.alias FROM name_aliases a JOIN tickers t USING (company_id)"
    ).fetchall():
        names.append((alias.lower(), tk))
    tickers = [row[0] for row in conn.execute("SELECT ticker FROM tickers").fetchall()]
    return names, tickers


def scan_entities(conn: psycopg.Connection, question: str) -> list[str]:
    """In-universe companies mentioned. Names matched case-insensitively; bare tickers only
    as uppercase words (so 'DE'/'CAT' don't match the words 'de'/'cat')."""
    names, tickers = _entity_scanners(conn)
    low = question.lower()
    found: list[str] = []
    for alias, tk in names:
        if len(alias) >= 3 and re.search(rf"\b{re.escape(alias)}\b", low) and tk not in found:
            found.append(tk)
    for tk in tickers:
        if re.search(rf"\b{tk}\b", question) and tk not in found:
            found.append(tk)
    return found


def _has_period(q: str) -> bool:
    return bool(re.search(r"fy ?20\d\d|fiscal ?20\d\d|q[1-4]\b|\b20\d\d\b", q))


def classify(question: str, tickers: list[str]) -> RouteDecision:
    """Pure routing decision given the question text and the resolved in-universe tickers
    (separated from DB entity-scanning so the routing rules are unit-testable)."""
    q = question.lower()

    # ---- 1. unanswerable classes (specific, high confidence) ----
    if re.search(r"\bcusip\b", q):
        return RouteDecision("unanswerable", 0.98, tickers, "CUSIP/identifier not stored (U7)")
    if re.search(r"price target|analyst|intraday|\d\s*(a|p)\.?m\b|stock price|share price", q):
        return RouteDecision("unanswerable", 0.9, tickers, "price / analyst-estimate data out of scope")
    if re.search(r"earnings call|q ?& ?a|conference call|ceo (say|said)|analyst q", q):
        return RouteDecision("unanswerable", 0.9, tickers, "earnings-call Q&A / transcript not ingested (U5)")
    if re.search(rf"\bin ({'|'.join(COUNTRIES)})\b", q) and re.search(_METRIC, q):
        return RouteDecision("unanswerable", 0.85, tickers, "geographic sub-segment not modeled (U10)")
    out = [w for w in OUT_OF_UNIVERSE if re.search(rf"\b{re.escape(w)}\b", q)]
    if out:
        if tickers:  # comparing an in-universe company against one we don't cover
            return RouteDecision("clarify", 0.8, tickers, f"{out[0].title()} is out of coverage; can address the covered leg only")
        return RouteDecision("unanswerable", 0.9, tickers, f"{out[0].title()} is outside the 10-company universe")

    narrative_intent = bool(re.search(_NARRATIVE, q))
    metric_intent = bool(re.search(_METRIC, q))

    # ---- 2. narrative intent wins over graph keywords (a 'supply-chain risk' is narrative) ----
    if narrative_intent and not re.search(r"which of|trace the|relationship between", q):
        return RouteDecision("narrative", 0.85, tickers, "qualitative / narrative question")

    # ---- 3. graph (relational) ----
    if re.search(_GRAPH, q):
        return RouteDecision("graph", 0.85, tickers, "relational/graph query — unanswerable until M2")

    # ---- 4. clarify (ambiguity — design §4.6/§6.6) ----
    if re.search(r"q[1-4]\s*20\d\d", q) and "fy" not in q:
        return RouteDecision("clarify", 0.75, tickers, "'Q# YYYY' is ambiguous: fiscal vs calendar quarter")
    if len(tickers) >= 2 and re.search(r"quarter|q[1-4]", q) and "fy" not in q:
        return RouteDecision("clarify", 0.7, tickers, "cross-company quarter misalignment — fiscal periods differ")
    if re.search(r"\bin 20\d\d\b", q) and metric_intent and not re.search(r"fiscal|fy", q):
        return RouteDecision("clarify", 0.65, tickers, "bare calendar year is ambiguous vs the fiscal year")
    if re.search(r"gross (margin|profit)", q) and "JPM" in tickers:
        return RouteDecision("clarify", 0.75, tickers, "JPMorgan is a bank — no gross margin; not comparable")
    if metric_intent and tickers and not _has_period(q):
        return RouteDecision("clarify", 0.6, tickers, "metric without a period — needs the fiscal period (and basis)")

    # ---- 5. segment & point-in-time preliminary → narrative path for M0 (ADR-0013) ----
    if re.search(_SEGMENT, q):
        return RouteDecision("narrative", 0.7, tickers, "segment question → narrative path for M0 (#13)")
    if re.search(r"as of|had .*(reported|announced)|announced", q):
        return RouteDecision("narrative", 0.7, tickers, "point-in-time preliminary → press-release retrieval")

    # ---- 6. metric (SQL path) ----
    if metric_intent and tickers:
        return RouteDecision("metric", 0.85, tickers, "quantitative → exact-numbers SQL path")

    # ---- 7. default ----
    return RouteDecision("hybrid", 0.5, tickers, "unclear → hybrid (both legs), reconcile at generation")


def route(conn: psycopg.Connection, question: str) -> RouteDecision:
    """Resolve entities deterministically, then classify (design §6.0 — resolution first)."""
    return classify(question, scan_entities(conn, question))
