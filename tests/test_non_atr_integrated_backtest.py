import pandas as pd
import pytest

from tools.research.non_atr_integrated_backtest import load_complete_tickers, run_backtest


def test_loader_excludes_ticker_with_missing_expected_session(tmp_path):
    path = tmp_path / "prices.csv"
    pd.DataFrame([
        {"Date": "2020-01-01", "Ticker": "AAA", "Adj Close": 10},
        {"Date": "2020-01-02", "Ticker": "AAA", "Adj Close": 11},
        {"Date": "2020-01-03", "Ticker": "AAA", "Adj Close": 12},
        {"Date": "2020-01-01", "Ticker": "BBB", "Adj Close": 20},
        {"Date": "2020-01-03", "Ticker": "BBB", "Adj Close": 22},
        {"Date": "2020-01-02", "Ticker": "CCC", "Adj Close": 30},
        {"Date": "2020-01-03", "Ticker": "CCC", "Adj Close": 31},
    ]).to_csv(path, index=False)
    eligible, audit = load_complete_tickers(path, min_rows=2)
    assert list(eligible) == ["AAA", "CCC"]
    assert audit.set_index("Ticker").loc["BBB", "reason"] == "incomplete_expected_session_history:1_missing_of_3"
    assert audit.set_index("Ticker").loc["CCC", "status"] == "eligible"


def test_runner_writes_audit_and_metrics(tmp_path):
    source = tmp_path / "prices.csv"
    output = tmp_path / "out"
    dates = pd.date_range("2018-01-01", periods=20, freq="D")
    pd.DataFrame({
        "Date": list(dates) * 2,
        "Ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
        "Adj Close": list(range(100, 120)) + list(range(80, 100)),
    }).to_csv(source, index=False)
    result = run_backtest(source, output, min_rows=10, min_train_rows=10, test_rows=5)
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



def test_pit_membership_checks_only_expected_member_sessions(tmp_path, monkeypatch):
    from datetime import date
    from tools.research import non_atr_integrated_backtest as runner
    from tools.research.pit_membership import MembershipInterval

    source = tmp_path / "prices.csv"
    spy = tmp_path / "spy.csv"
    pd.DataFrame([
        {"Date": "2024-01-01", "Ticker": "AAA", "Adj Close": 10},
        {"Date": "2024-01-02", "Ticker": "AAA", "Adj Close": 11},
        {"Date": "2024-01-03", "Ticker": "AAA", "Adj Close": 12},
    ]).to_csv(source, index=False)
    pd.DataFrame({"Date": ["2024-01-01", "2024-01-02", "2024-01-03"]}).to_csv(spy, index=False)
    membership = {"AAA": [MembershipInterval("AAA", date(2024, 1, 2), None)]}
    monkeypatch.setattr(runner, "load_multi_index_membership", lambda *args: membership)
    paths = tuple(tmp_path / name for name in ("sp500.csv", "aliases.csv", "nasdaq.csv", "dow.csv"))
    eligible, audit = runner.load_complete_tickers(
        source, min_rows=2, spy_path=spy, membership_paths=paths
    )
    assert audit.set_index("Ticker").loc["AAA", "status"] == "eligible"
    assert eligible["AAA"]["Date"].dt.strftime("%Y-%m-%d").tolist() == ["2024-01-02", "2024-01-03"]


def test_pit_membership_audits_ticker_with_zero_downloaded_rows(tmp_path, monkeypatch):
    from datetime import date
    from tools.research import non_atr_integrated_backtest as runner
    from tools.research.pit_membership import MembershipInterval

    source = tmp_path / "prices.csv"
    spy = tmp_path / "spy.csv"
    pd.DataFrame([
        {"Date": "2024-01-01", "Ticker": "AAA", "Adj Close": 10},
        {"Date": "2024-01-02", "Ticker": "AAA", "Adj Close": 11},
        {"Date": "2024-01-03", "Ticker": "AAA", "Adj Close": 12},
    ]).to_csv(source, index=False)
    pd.DataFrame({"Date": ["2024-01-01", "2024-01-02", "2024-01-03"]}).to_csv(spy, index=False)
    membership = {
        "AAA": [MembershipInterval("AAA", date(2024, 1, 1), None)],
        "MISSING": [MembershipInterval("MISSING", date(2024, 1, 1), None)],
    }
    monkeypatch.setattr(runner, "load_multi_index_membership", lambda *args: membership)
    paths = tuple(tmp_path / name for name in ("sp500.csv", "aliases.csv", "nasdaq.csv", "dow.csv"))
    eligible, audit = runner.load_complete_tickers(
        source, min_rows=2, spy_path=spy, membership_paths=paths
    )
    missing = audit.set_index("Ticker").loc["MISSING"]
    assert missing["status"] == "excluded"
    assert missing["rows"] == 0
    assert missing["reason"] == (
        "incomplete_expected_session_history:3_missing_of_3;no_downloaded_price_rows"
    )
    assert "MISSING" not in eligible


def test_pit_membership_excludes_missing_expected_member_session(tmp_path, monkeypatch):
    from datetime import date
    from tools.research import non_atr_integrated_backtest as runner
    from tools.research.pit_membership import MembershipInterval

    source = tmp_path / "prices.csv"
    spy = tmp_path / "spy.csv"
    pd.DataFrame([
        {"Date": "2024-01-01", "Ticker": "AAA", "Adj Close": 10},
        {"Date": "2024-01-03", "Ticker": "AAA", "Adj Close": 12},
    ]).to_csv(source, index=False)
    pd.DataFrame({"Date": ["2024-01-01", "2024-01-02", "2024-01-03"]}).to_csv(spy, index=False)
    membership = {"AAA": [MembershipInterval("AAA", date(2024, 1, 1), None)]}
    monkeypatch.setattr(runner, "load_multi_index_membership", lambda *args: membership)
    paths = tuple(tmp_path / name for name in ("sp500.csv", "aliases.csv", "nasdaq.csv", "dow.csv"))
    eligible, audit = runner.load_complete_tickers(
        source, min_rows=2, spy_path=spy, membership_paths=paths
    )
    row = audit.set_index("Ticker").loc["AAA"]
    assert row["status"] == "excluded"
    assert "1_missing_of_3" in row["reason"]
    assert eligible == {}
