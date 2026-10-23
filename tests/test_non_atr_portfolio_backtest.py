import pandas as pd
import pytest

from tools.research.non_atr_portfolio_backtest import combine_equal_weight_portfolio


def test_equal_weight_portfolio_keeps_cash_and_charges_weight_changes():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    panel = pd.DataFrame([
        {"Date": dates[0], "Ticker": "AAA", "daily_return": 0.10, "held_position": 1.0},
        {"Date": dates[0], "Ticker": "BBB", "daily_return": 0.20, "held_position": 0.0},
        {"Date": dates[1], "Ticker": "AAA", "daily_return": 0.00, "held_position": 1.0},
        {"Date": dates[1], "Ticker": "BBB", "daily_return": 0.10, "held_position": 1.0},
    ])
    zero_cost = combine_equal_weight_portfolio(panel, dates, one_way_cost_bps=0)
    five_bps = combine_equal_weight_portfolio(panel, dates, one_way_cost_bps=5)

    assert zero_cost.loc[dates[0], "gross_return"] == pytest.approx(0.05)
    assert zero_cost.loc[dates[0], "exposure"] == pytest.approx(0.5)
    assert zero_cost.loc[dates[1], "gross_return"] == pytest.approx(0.05)
    assert five_bps.loc[dates[1], "net_return"] < zero_cost.loc[dates[1], "net_return"]
    assert five_bps.loc[dates[1], "turnover"] > 0


def test_rejects_bad_positions_and_negative_costs():
    dates = pd.to_datetime(["2024-01-02"])
    panel = pd.DataFrame([{"Date": dates[0], "Ticker": "AAA", "daily_return": 0.0, "held_position": 1.2}])
    with pytest.raises(ValueError, match="between 0 and 1"):
        combine_equal_weight_portfolio(panel, dates, one_way_cost_bps=0)
    panel.loc[0, "held_position"] = 1.0
    with pytest.raises(ValueError, match="cannot be negative"):
        combine_equal_weight_portfolio(panel, dates, one_way_cost_bps=-1)


def test_reindexes_missing_members_to_zero_weight():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    panel = pd.DataFrame([
        {"Date": dates[0], "Ticker": "AAA", "daily_return": 0.0, "held_position": 1.0},
        {"Date": dates[1], "Ticker": "AAA", "daily_return": 0.0, "held_position": 1.0},
    ])
    portfolio = combine_equal_weight_portfolio(panel, dates, one_way_cost_bps=0)
    assert portfolio.loc[dates[2], "exposure"] == 0.0
    assert portfolio.loc[dates[2], "active_tickers"] == 0

from tools.research.non_atr_portfolio_backtest import apply_risk_controls


def test_risk_controls_cap_exposure_and_pause_after_drawdown():
    dates = pd.date_range("2024-01-02", periods=6, freq="B")
    portfolio = pd.DataFrame({
        "gross_return": [0.0, -0.60, 0.01, 0.01, 0.01, 0.01],
        "turnover": [0.5] * 6,
        "cost": [0.00025] * 6,
        "net_return": [0.0, -0.60, 0.01, 0.01, 0.01, 0.01],
        "exposure": [0.5] * 6,
        "active_tickers": [10] * 6,
    }, index=dates)
    controlled = apply_risk_controls(
        portfolio,
        one_way_cost_bps=5,
        target_annual_volatility=1.0,
        volatility_lookback=2,
        max_exposure=0.25,
        drawdown_limit=0.10,
        cooldown_sessions=2,
    )
    assert controlled["exposure"].iloc[0] == pytest.approx(0.25)
    # The first session's loss is observed only after that session closes;
    # the next session therefore enters the cooldown in cash.
    assert controlled["risk_scale"].iloc[2] == pytest.approx(0.0)
    assert controlled["exposure"].iloc[2] == pytest.approx(0.0)
    assert controlled["risk_scale"].iloc[3] == pytest.approx(0.0)
    assert controlled["risk_scale"].iloc[4] > 0.0


def test_risk_controls_reject_invalid_parameters():
    dates = pd.date_range("2024-01-02", periods=2, freq="B")
    portfolio = pd.DataFrame({
        "gross_return": [0.0, 0.0],
        "turnover": [0.0, 0.0],
        "cost": [0.0, 0.0],
        "net_return": [0.0, 0.0],
        "exposure": [0.0, 0.0],
    }, index=dates)
    with pytest.raises(ValueError, match="max_exposure"):
        apply_risk_controls(portfolio, one_way_cost_bps=5, max_exposure=0)
