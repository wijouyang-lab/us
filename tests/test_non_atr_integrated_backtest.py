import pandas as pd
import pytest

from tools.research.non_atr_integrated_backtest import load_complete_tickers, run_backtest


def test_later_listing_is_not_excluded_for_earlier_dates(tmp_path):
    prices = tmp_path / "prices.csv"
    sessions = tmp_path / "sessions.csv"
    pd.DataFrame([
        {"Date": "2020-01-01", "Ticker": "AAA", "Adj Close": 10},
        {"Date": "2020-01-02", "Ticker": "AAA", "Adj Close": 11},
        {"Date": "2020-01-03", "Ticker": "AAA", "Adj Close": 12},
        {"Date": "2020-01-02", "Ticker": "BBB", "Adj Close": 20},
        {"Date": "2020-01-03", "Ticker": "BBB", "Adj Close": 22},
    ]).to_csv(prices, index=False)
    pd.DataFrame({"Date": ["2020-01-01", "2020-01-02", "2020-01-03"]}).to_csv(sessions, index=False)
    eligible, audit = load_complete_tickers(prices, min_rows=2, sessions_path=sessions)
    assert list(eligible) == ["AAA", "BBB"]
    assert audit.set_index("Ticker").loc["BBB", "expected_sessions"] == 2


def test_missing_internal_market_session_is_excluded(tmp_path):
    prices = tmp_path / "prices.csv"
    sessions = tmp_path / "sessions.csv"
    pd.DataFrame([
        {"Date": "2020-01-01", "Ticker": "AAA", "Adj Close": 10},
        {"Date": "2020-01-03", "Ticker": "AAA", "Adj Close": 12},
    ]).to_csv(prices, index=False)
    pd.DataFrame({"Date": ["2020-01-01", "2020-01-02", "2020-01-03"]}).to_csv(sessions, index=False)
    eligible, audit = load_complete_tickers(prices, min_rows=2, sessions_path=sessions)
    assert eligible == {}
    assert audit.iloc[0]["missing_sessions"] == 1
    assert "missing_expected_market_sessions" in audit.iloc[0]["reason"]


def test_runner_writes_audit_and_metrics(tmp_path):
    source, sessions, output = tmp_path / "prices.csv", tmp_path / "sessions.csv", tmp_path / "out"
    dates = pd.date_range("2018-01-01", periods=20, freq="D")
    pd.DataFrame({"Date": list(dates) * 2, "Ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
                  "Adj Close": list(range(100, 120)) + list(range(80, 100))}).to_csv(source, index=False)
    pd.DataFrame({"Date": dates}).to_csv(sessions, index=False)
    result = run_backtest(source, output, min_rows=10, min_train_rows=10, test_rows=5, sessions_path=sessions)
    assert result == {"input_tickers": 2, "eligible_tickers": 2, "excluded_tickers": 0,
                      "metric_rows": 6, "oos_rows": 12}
    assert (output / "ticker_eligibility_audit.csv").exists()
    assert (output / "strategy_metrics.csv").exists()
    assert (output / "walk_forward_oos_metrics.csv").exists()


def test_loader_rejects_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"Date": ["2020-01-01"], "Ticker": ["AAA"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Adj Close"):
        load_complete_tickers(path)
