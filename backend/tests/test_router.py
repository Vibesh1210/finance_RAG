"""Router classification unit tests (pure: classify() takes pre-resolved tickers, no DB).
The full 60-question routing accuracy is measured by the Phase 5 gate."""

from __future__ import annotations

from us_rag.query.router import classify


def r(question, tickers):
    return classify(question, tickers).route


def test_metric_question_routes_to_sql():
    assert r("What was Apple's revenue for fiscal year 2025?", ["AAPL"]) == "metric"


def test_number_question_never_goes_to_text_only():
    # "what did X report as its Q4 revenue" is a number, not narrative
    assert r("What did Caterpillar report as its fourth-quarter 2024 revenue?", ["CAT"]) == "metric"


def test_supply_chain_risk_is_narrative_not_graph():
    assert r("What risks did Apple disclose about supply chain and manufacturing?", ["AAPL"]) == "narrative"


def test_relational_question_routes_to_graph():
    assert r("Which of Walmart's suppliers also supply Costco?", ["WMT", "COST"]) == "graph"


def test_segment_question_routes_narrative_for_m0():
    assert r("How did Apple's Services revenue compare to its Products revenue in fiscal 2025?", ["AAPL"]) == "narrative"


def test_unanswerable_classes():
    assert r("What is Apple's CUSIP number?", ["AAPL"]) == "unanswerable"
    assert r("What is the current analyst price target for Microsoft?", ["MSFT"]) == "unanswerable"
    assert r("What was Tesla's revenue for fiscal year 2025?", []) == "unanswerable"
    assert r("What was Apple's revenue specifically in Germany in fiscal 2025?", ["AAPL"]) == "unanswerable"


def test_ambiguity_routes_to_clarify():
    assert r("What was Apple's Q3 2024 revenue?", ["AAPL"]) == "clarify"          # fiscal vs calendar
    assert r("What was Walmart's revenue?", ["WMT"]) == "clarify"                  # no period
    assert r("What was NVIDIA's revenue in 2024?", ["NVDA"]) == "clarify"          # bare calendar year
    assert r("Compare JPMorgan's gross margin to Apple's for fiscal 2025.", ["JPM", "AAPL"]) == "clarify"


def test_out_of_universe_leg_in_a_compare_clarifies():
    assert r("Compare ExxonMobil's revenue to Chevron's for fiscal 2024.", ["XOM"]) == "clarify"
