"""Golden-bank schema + loader (execution plan Phase 3).

The bank is YAML so it is human-readable and human-labelled. Every question is
point-in-time (`as_of`). Factual questions carry gold PASSAGES (accession + section);
quant questions carry a gold VALUE + provenance — the quant gold stays coupled to the
Phase 2 spot-checks (DECISIONS #12), so it is provisional until those land.

`gold_keys` yields the (accession, section) tuples the metrics score against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

# the eight factual shapes the bank must cover (execution plan Phase 3 distribution)
CATEGORIES = {
    "direct_metric",
    "fiscal_trap",
    "point_in_time",
    "segment",
    "cross_company",
    "narrative",
    "graph",
    "unanswerable",
}
EXPECTED = {"retrieve", "answer", "abstain", "typed_refusal", "clarify"}


@dataclass(frozen=True)
class GoldPassage:
    accession: str
    section: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.accession, self.section)


@dataclass
class Question:
    id: str
    question: str
    kind: str  # "factual" | "quant"
    category: str
    as_of: date
    company: str | None = None
    expected: str = "retrieve"  # retrieve | answer | abstain | typed_refusal
    gold: list[GoldPassage] = field(default_factory=list)  # factual: relevant passages
    gold_value: str | None = None  # quant: the exact answer
    unit: str | None = None
    provenance: dict | None = None

    @property
    def gold_keys(self) -> set[tuple[str, str]]:
        return {p.key for p in self.gold}


def _parse(entry: dict, kind: str) -> Question:
    as_of = entry["as_of"]
    if not isinstance(as_of, date):
        as_of = date.fromisoformat(str(as_of))
    q = Question(
        id=entry["id"],
        question=entry["question"],
        kind=kind,
        category=entry["category"],
        as_of=as_of,
        company=entry.get("company"),
        expected=entry.get("expected", "retrieve" if kind == "factual" else "answer"),
        gold=[GoldPassage(g["accession"], g["section"]) for g in entry.get("gold", [])],
        gold_value=entry.get("gold_value"),
        unit=entry.get("unit"),
        provenance=entry.get("provenance"),
    )
    _validate(q)
    return q


def _validate(q: Question) -> None:
    if q.category not in CATEGORIES:
        raise ValueError(f"{q.id}: unknown category {q.category!r}")
    if q.expected not in EXPECTED:
        raise ValueError(f"{q.id}: unknown expected {q.expected!r}")
    if q.expected == "retrieve" and not q.gold:
        raise ValueError(f"{q.id}: expected to retrieve but labels no gold passages")
    if q.kind == "quant" and q.expected == "answer" and q.gold_value is None:
        raise ValueError(f"{q.id}: quant question expected to answer needs a gold_value")


def load_bank(path: str | Path, kind: str) -> list[Question]:
    """Load and validate a bank file. `kind` is 'factual' or 'quant'."""
    entries = yaml.safe_load(Path(path).read_text()) or []
    return [_parse(e, kind) for e in entries]
