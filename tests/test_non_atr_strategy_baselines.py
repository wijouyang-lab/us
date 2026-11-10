import pandas as pd
import pytest

from tools.research.non_atr_strategy_baselines import build_strategy_returns, summarize_returns


def test_signals_do_not_earn_same_session_return():
    prices = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=8, freq="D"),
        "Adj Close": [100, 101, 102, 103, 104, 105, 106, 107],
    })
    result = build_strategy_returns(
        prices, momentum_lookback=2, trend_fast=2, trend_slow=3,
        mean_reversion_lookback=3,
    )
    assert result.loc[0, "momentum_return"] == 0.0
    # Signal known after t=2 close must not earn the t=2 close-to-close return.
    assert result.loc[2, "momentum_position"] == 1.0
    assert result.loc[2, "momentum_return"] == 0.0
    # It can first earn the following session's return (102 -> 103).
    assert result.loc[3, "momentum_return"] == pytest.approx(103 / 102 - 1)


def test_invalid_windows_raise():
    prices = pd.DataFrame({"Date": ["2024-01-01"], "Adj Close": [10]})
    with pytest.raises(ValueError):
        build_strategy_returns(prices, trend_fast=200, trend_slow=50)


def test_summary_empty_and_drawdown():
    assert summarize_returns(pd.Series(dtype=float))["observations"] == 0
    summary = summarize_returns(pd.Series([0.1, -0.2, 0.05]))
    assert summary["observations"] == 3
    assert summary["max_drawdown"] < 0
