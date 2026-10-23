import pandas as pd
import pytest

from tools.research.non_atr_robustness_report import build_robustness_report, render_markdown


def sample_metrics():
    return pd.DataFrame([
        {"Ticker":"AAA","strategy":"mean_reversion","split":1,"test_start":"2020-01-01","test_end":"2020-12-31","observations":252,"total_return":0.10,"annualized_return":0.10,"sharpe_zero_rf":0.7,"max_drawdown":-0.12,"cost_bps_one_way":5},
        {"Ticker":"BBB","strategy":"mean_reversion","split":1,"test_start":"2020-01-01","test_end":"2020-12-31","observations":252,"total_return":-0.05,"annualized_return":-0.05,"sharpe_zero_rf":-0.1,"max_drawdown":-0.20,"cost_bps_one_way":5},
        {"Ticker":"AAA","strategy":"mean_reversion","split":2,"test_start":"2021-01-01","test_end":"2021-12-31","observations":252,"total_return":0.02,"annualized_return":0.02,"sharpe_zero_rf":0.2,"max_drawdown":-0.08,"cost_bps_one_way":5},
        {"Ticker":"AAA","strategy":"momentum","split":1,"test_start":"2020-01-01","test_end":"2020-12-31","observations":252,"total_return":-0.10,"annualized_return":-0.10,"sharpe_zero_rf":-0.5,"max_drawdown":-0.30,"cost_bps_one_way":5},
    ])


def test_aggregates_strategy_and_window_stability():
    strategies, windows = build_robustness_report(sample_metrics())
    mr = strategies.set_index("strategy").loc["mean_reversion"]
    assert mr["oos_rows"] == 3
    assert mr["unique_tickers"] == 2
    assert mr["positive_window_rate"] == pytest.approx(2 / 3)
    first_window = windows[(windows["strategy"] == "mean_reversion") & (windows["split"] == 1)].iloc[0]
    assert first_window["ticker_rows"] == 2
    assert first_window["positive_ticker_rate"] == pytest.approx(0.5)


def test_rejects_missing_columns_and_invalid_drawdown():
    with pytest.raises(ValueError, match="missing columns"):
        build_robustness_report(pd.DataFrame({"Ticker":["AAA"]}))
    data = sample_metrics()
    data.loc[0, "max_drawdown"] = 0.01
    with pytest.raises(ValueError, match="drawdowns"):
        build_robustness_report(data)


def test_report_includes_limitations():
    strategy, windows = build_robustness_report(sample_metrics())
    report = render_markdown(strategy, windows)
    assert "not independent observations" in report
    assert "cost-sensitivity study" in report
