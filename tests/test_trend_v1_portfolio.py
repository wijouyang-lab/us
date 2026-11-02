# -*- coding: utf-8 -*-
"""Portfolio accounting and risk tests for Trend V1."""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from trend_v1.backtest import SimConfig, equal_alloc, simulate  # noqa: E402
from trend_v1.risk import RiskConfig, allocate, defense_cap, defense_state  # noqa: E402


def test_defense_ladder():
    assert defense_cap(0.0) == 1.0
    assert defense_cap(0.06) == 0.75
    assert defense_cap(0.09) == 0.50
    assert defense_cap(0.11) == 0.25
    assert defense_cap(0.13) == 0.0
    assert defense_state(0.16) == "HARD_RISK_BREACH"


def test_no_candidates_is_all_cash():
    assert equal_alloc(pd.DataFrame(columns=["ticker"]), None, 0.0)[0] == {}


def test_weights_and_caps():
    dates = pd.bdate_range("2020-01-01", periods=90)
    closes = pd.DataFrame({f"T{i}": np.linspace(100, 110, len(dates)) * (1 + i * 0.01) for i in range(6)}, index=dates)
    cand = pd.DataFrame({"ticker": list(closes.columns), "Score": np.arange(6)})
    w, diag = allocate(cand, closes, dates[-1], 0.0, RiskConfig(max_weight=0.10, max_group_weight=0.20))
    assert sum(w.values()) <= 1.0 + 1e-9
    assert all(v <= 0.10 + 1e-9 for v in w.values())


def test_correlated_group_is_capped():
    dates = pd.bdate_range("2020-01-01", periods=90)
    base = np.linspace(100, 120, len(dates)) + np.sin(np.arange(len(dates)))
    closes = pd.DataFrame({t: base * (1 + i * 0.001) for i, t in enumerate(["A", "B", "C", "D"])}, index=dates)
    w, _ = allocate(pd.DataFrame({"ticker": ["A", "B", "C", "D"], "Score": [4, 3, 2, 1]}), closes, dates[-1], 0.0,
                    RiskConfig(max_weight=0.5, max_group_weight=0.20, corr_threshold=0.5))
    assert sum(w.values()) <= 0.20 + 1e-9


def test_cash_and_cost_accounting():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    opens = pd.DataFrame({"A": [100.0, 100.0, 100.0]}, index=dates)
    closes = pd.DataFrame({"A": [110.0, 110.0, 110.0]}, index=dates)
    events = {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]})}
    daily, _ = simulate(opens, closes, events, lambda c, d, dd: ({"A": 1.0}, {"reason": "OK", "defense": "NORMAL"}),
                        SimConfig(cost_bps=10))
    assert daily.cash.min() >= -1e-9
    assert daily.nav.iloc[-1] > 1.0


def test_no_negative_cash_on_buy():
    dates = pd.to_datetime(["2024-01-02"])
    opens = pd.DataFrame({"A": [100.0]}, index=dates)
    closes = pd.DataFrame({"A": [100.0]}, index=dates)
    daily, _ = simulate(opens, closes, {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]})},
                        lambda c, d, dd: ({"A": 1.0}, {"reason": "OK", "defense": "NORMAL"}), SimConfig(cost_bps=50))
    assert daily.cash.iloc[0] >= -1e-9
    assert daily.nav.iloc[0] > 0


def test_risk_uses_only_past_prices():
    dates = pd.bdate_range("2020-01-01", periods=80)
    closes = pd.DataFrame({"A": np.linspace(100, 120, 80), "B": np.linspace(100, 115, 80)}, index=dates)
    cand = pd.DataFrame({"ticker": ["A", "B"], "Score": [2, 1]})
    w1, _ = allocate(cand, closes, dates[60], 0.0)
    future = closes.copy(); future.loc[future.index > dates[60]] *= 10
    w2, _ = allocate(cand, future, dates[60], 0.0)
    assert w1 == w2
