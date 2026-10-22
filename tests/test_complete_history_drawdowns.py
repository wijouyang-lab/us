from datetime import date

import pandas as pd

from tools.research.analyze_complete_history_drawdowns import build_reports
from tools.research.pit_membership import MembershipInterval


def test_build_reports_filters_low_coverage_and_calculates_adjusted_drawdown():
    sessions = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
    spy = pd.DataFrame({"Date": [day.isoformat() for day in sessions]})
    prices = pd.DataFrame([
        {"Date": sessions[0].isoformat(), "Ticker": "AAA", "Adj Close": 100.0},
        {"Date": sessions[1].isoformat(), "Ticker": "AAA", "Adj Close": 80.0},
        {"Date": sessions[2].isoformat(), "Ticker": "AAA", "Adj Close": 90.0},
        {"Date": sessions[0].isoformat(), "Ticker": "BBB", "Adj Close": 10.0},
    ])
    membership = {
        "AAA": [MembershipInterval("AAA", sessions[0], None)],
        "BBB": [MembershipInterval("BBB", sessions[0], None)],
    }

    coverage, drawdowns, summary = build_reports(
        prices, spy, membership, min_coverage=0.90, min_valid_rows=2
    )

    by_ticker = coverage.set_index("Ticker")
    assert bool(by_ticker.loc["AAA", "Eligible_For_Drawdown_Research"])
    assert not bool(by_ticker.loc["BBB", "Eligible_For_Drawdown_Research"])
    assert by_ticker.loc["BBB", "Exclusion_Reason"] == "coverage_below_threshold"

    row = drawdowns.set_index("Ticker").loc["AAA"]
    assert row["Max_Drawdown_Pct"] == -20.0
    assert row["Peak_Date"] == "2024-01-02"
    assert row["Trough_Date"] == "2024-01-03"
    assert row["Recovered"] is False or not row["Recovered"]
    assert summary["eligible_tickers"] == 1
    assert summary["excluded_tickers"] == 1


def test_build_reports_rejects_invalid_coverage_threshold():
    with __import__("pytest").raises(ValueError, match="min_coverage"):
        build_reports(
            pd.DataFrame(columns=["Date", "Ticker", "Adj Close"]),
            pd.DataFrame({"Date": ["2024-01-02"]}),
            {},
            min_coverage=0,
        )
