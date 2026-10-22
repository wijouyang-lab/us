from datetime import date

import pandas as pd

from tools.research.analyze_complete_history_drawdowns import build_reports
from tools.research.pit_membership import MembershipInterval


def test_complete_coverage_keeps_only_tickers_with_every_expected_session():
    sessions = pd.DataFrame({"Date": ["2024-01-02", "2024-01-03", "2024-01-04"]})
    prices = pd.DataFrame(
        [
            {"Date": "2024-01-02", "Ticker": "AAA", "Adj Close": 10.0},
            {"Date": "2024-01-03", "Ticker": "AAA", "Adj Close": 11.0},
            {"Date": "2024-01-04", "Ticker": "AAA", "Adj Close": 12.0},
            {"Date": "2024-01-02", "Ticker": "BBB", "Adj Close": 10.0},
            {"Date": "2024-01-04", "Ticker": "BBB", "Adj Close": 12.0},
        ]
    )
    membership = {
        "AAA": [MembershipInterval("AAA", date(2024, 1, 2), date(2024, 1, 5))],
        "BBB": [MembershipInterval("BBB", date(2024, 1, 2), date(2024, 1, 5))],
    }

    coverage, drawdowns, summary = build_reports(
        prices, sessions, membership, min_coverage=1.0, min_valid_rows=2
    )

    status = coverage.set_index("Ticker")["Eligible_For_Drawdown_Research"].to_dict()
    assert status == {"AAA": True, "BBB": False}
    assert drawdowns["Ticker"].tolist() == ["AAA"]
    assert summary["eligible_tickers"] == 1
    assert summary["excluded_tickers"] == 1


def test_recent_member_can_be_complete_within_its_actual_membership_window():
    sessions = pd.DataFrame({"Date": ["2024-01-02", "2024-01-03", "2024-01-04"]})
    prices = pd.DataFrame(
        [
            {"Date": "2024-01-03", "Ticker": "NEW", "Adj Close": 20.0},
            {"Date": "2024-01-04", "Ticker": "NEW", "Adj Close": 21.0},
        ]
    )
    membership = {
        "NEW": [MembershipInterval("NEW", date(2024, 1, 3), date(2024, 1, 5))]
    }

    coverage, drawdowns, summary = build_reports(
        prices, sessions, membership, min_coverage=1.0, min_valid_rows=2
    )

    assert coverage.iloc[0]["Session_Coverage"] == 1.0
    assert coverage.iloc[0]["Eligible_For_Drawdown_Research"]
    assert drawdowns["Ticker"].tolist() == ["NEW"]
    assert summary["eligible_tickers"] == 1
