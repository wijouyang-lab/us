from __future__ import annotations

import pandas as pd

from tools.research.event_factor_backtest import evaluate


def test_event_factor_backtest_excludes_unknown_and_enters_after_decision(tmp_path):
    signal_path = tmp_path / "signals.csv"
    price_path = tmp_path / "prices.csv"
    decision = "2026-01-02T12:00:00Z"
    signals = []
    prices = []
    for i in range(8):
        ticker = f"T{i}"
        signals.append({
            "decision_at": decision, "ticker": ticker,
            "event_score": i, "coverage_status": "available",
        })
        # Same-day close precedes the decision timestamp and must not be entry.
        prices.extend([
            {"date": "2026-01-02T00:00:00Z", "ticker": ticker, "close": 100},
            {"date": "2026-01-03T00:00:00Z", "ticker": ticker, "close": 110 if i >= 4 else 90},
            {"date": "2026-01-04T00:00:00Z", "ticker": ticker, "close": 121 if i >= 4 else 81},
        ])
    signals.append({
        "decision_at": decision, "ticker": "UNKNOWN",
        "event_score": 1000, "coverage_status": "missing",
    })
    signals.append({
        "decision_at": decision, "ticker": "NOSCORE",
        "event_score": "", "coverage_status": "available",
    })
    signals_df = pd.DataFrame(signals)
    prices_df = pd.DataFrame(prices)
    signals_df.to_csv(signal_path, index=False)
    prices_df.to_csv(price_path, index=False)

    result = evaluate(
        str(signal_path), str(price_path), horizon=1,
        cost_bps_per_side=0, quantile=0.25, min_names_per_side=2,
    )

    assert result["status"] == "evaluated"
    assert result["excluded_unknown_coverage"] == 1
    assert result["excluded_missing_score"] == 1
    assert result["decision_dates_tested"] == 1
    row = result["per_decision_date"][0]
    assert row["long_tickers"] == ["T6", "T7"]
    assert row["short_tickers"] == ["T0", "T1"]
    assert row["long_short_gross_return"] > 0
    assert result["production_signal_generated"] is False


def test_event_factor_backtest_returns_insufficient_data_for_missing_coverage(tmp_path):
    signal_path = tmp_path / "signals.csv"
    price_path = tmp_path / "prices.csv"
    pd.DataFrame([{
        "decision_at": "2026-01-02T12:00:00Z", "ticker": "A",
        "event_score": 1, "coverage_status": "missing",
    }]).to_csv(signal_path, index=False)
    pd.DataFrame([
        {"date": "2026-01-03T00:00:00Z", "ticker": "A", "close": 10},
        {"date": "2026-01-04T00:00:00Z", "ticker": "A", "close": 11},
    ]).to_csv(price_path, index=False)

    result = evaluate(str(signal_path), str(price_path), horizon=1)
    assert result["status"] == "insufficient_data"
    assert result["decision_dates_tested"] == 0
    assert result["excluded_unknown_coverage"] == 1
