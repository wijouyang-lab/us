# -*- coding: utf-8 -*-
"""Regression tests for the Phase 3.2 audit fixes."""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from trend_v1.backtest import SimConfig, StalePriceError, simulate  # noqa: E402
from trend_v1.risk import RiskConfig, allocate  # noqa: E402


def test_drawdown_is_positive_and_defense_engages():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    opens = pd.DataFrame({"A": [100.0, 90.0, 90.0]}, index=dates)
    closes = pd.DataFrame({"A": [100.0, 90.0, 90.0]}, index=dates)
    seen = []
    events = {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]}),
              dates[2]: pd.DataFrame({"ticker": ["A"], "Score": [1]})}

    def alloc(c, dt, dd):
        seen.append(dd)
        return {"A": 1.0}, {"reason": "OK", "defense": "X"}

    simulate(opens, closes, events, alloc, SimConfig(cost_bps=0))
    assert seen[0] == 0.0
    assert seen[1] > 0.05


def test_rank_affects_weights_with_equal_vol():
    dates = pd.bdate_range("2020-01-01", periods=80)
    base = np.linspace(100, 120, len(dates))
    closes = pd.DataFrame({"A": base, "B": base}, index=dates)
    cand = pd.DataFrame({"ticker": ["A", "B"], "Score": [0.9, 0.1]})
    w, _ = allocate(cand, closes, dates[-1], 0.0, RiskConfig(max_weight=0.9))
    assert w["A"] > w["B"]


def test_empty_event_liquidates():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    opens = pd.DataFrame({"A": [100.0, 100.0]}, index=dates)
    closes = pd.DataFrame({"A": [100.0, 100.0]}, index=dates)
    events = {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]}),
              dates[1]: pd.DataFrame(columns=["ticker", "Score"])}
    daily, _ = simulate(opens, closes, events, lambda c, d, dd: ({"A": 1.0} if len(c) else {}, {"reason": "OK", "defense": "NORMAL"}),
                        SimConfig(cost_bps=0))
    assert daily.n_holdings.iloc[-1] == 0
    assert daily.cash.iloc[-1] == daily.nav.iloc[-1]


def test_daily_holdings_persist_between_rebalances():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    opens = pd.DataFrame({"A": [100.0, 100.0, 100.0]}, index=dates)
    closes = pd.DataFrame({"A": [100.0, 101.0, 102.0]}, index=dates)
    daily, _ = simulate(opens, closes, {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]})},
                        lambda c, d, dd: ({"A": 1.0}, {"reason": "OK", "defense": "NORMAL"}), SimConfig(cost_bps=0))
    assert daily.n_holdings.tolist() == [1, 1, 1]


def test_stale_price_fails_closed():
    dates = pd.bdate_range("2024-01-01", periods=10)
    raw = pd.DataFrame({"A": [100.0] + [np.nan] * 7 + [100.0, 100.0]}, index=dates)
    opens = pd.DataFrame({"A": 100.0}, index=dates)
    closes = raw.ffill(limit=5)
    try:
        simulate(opens, closes, {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]})},
                 lambda c, d, dd: ({"A": 1.0}, {"reason": "OK", "defense": "NORMAL"}),
                 SimConfig(cost_bps=0), raw_closes=raw, max_stale_days=5)
    except StalePriceError:
        pass
    else:
        raise AssertionError("stale price accepted")


def test_single_asset_is_allowed():
    dates = pd.bdate_range("2020-01-01", periods=80)
    closes = pd.DataFrame({"A": np.linspace(100, 120, 80)}, index=dates)
    w, diag = allocate(pd.DataFrame({"ticker": ["A"], "Score": [1]}), closes, dates[-1], 0.0)
    assert diag["reason"] == "OK"
    assert 0 < sum(w.values()) <= 1


def test_cost_is_charged_exactly_once():
    dates = pd.to_datetime(["2024-01-02"])
    opens = pd.DataFrame({"A": [100.0]}, index=dates)
    closes = pd.DataFrame({"A": [100.0]}, index=dates)
    daily, _ = simulate(opens, closes, {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]})},
                        lambda c, d, dd: ({"A": 1.0}, {"reason": "OK", "defense": "NORMAL"}),
                        SimConfig(cost_bps=10))
    assert abs(daily.cost.iloc[0] - 0.001) < 2e-6
    assert abs(daily.cash.iloc[0]) < 2e-6
    assert abs(daily.buy.iloc[0] - 0.999) < 2e-6


import pytest
from trend_v1.risk import defense_state


@pytest.mark.parametrize("drop,expected", [
    (0.06, "DEFENSIVE_75"), (0.09, "DEFENSIVE_50"), (0.11, "DEFENSIVE_25"),
    (0.13, "CASH_DEFENSE"), (0.16, "HARD_RISK_BREACH")])
def test_each_defense_threshold_through_simulate(drop, expected):
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    px = 100.0 * (1 - drop)
    opens = pd.DataFrame({"A": [100.0, px, px]}, index=dates)
    closes = pd.DataFrame({"A": [100.0, px, px]}, index=dates)
    seen = []
    events = {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]}),
              dates[2]: pd.DataFrame({"ticker": ["A"], "Score": [1]})}
    def alloc(c, dt, dd):
        seen.append(dd)
        return {"A": 1.0}, {"reason": "OK", "defense": "X"}
    simulate(opens, closes, events, alloc, SimConfig(cost_bps=0))
    assert abs(seen[1] - drop) < 1e-6
    assert defense_state(seen[1]) == expected
