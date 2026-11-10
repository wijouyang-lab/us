# -*- coding: utf-8 -*-
"""Tests for non-overlapping 60D volatility portfolios."""

import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from volatility_portfolio_validation import build_schedule, cost_units, metrics, weights_inv_vol  # noqa: E402


def test_schedule_is_non_overlapping_and_uses_next_open():
    dates = pd.bdate_range("2018-01-01", periods=400)
    s = build_schedule(dates)
    assert len(s) >= 5
    for i, (sig, entry, exit_) in enumerate(s):
        assert entry > sig
        assert (exit_ - entry).days > 0
        if i:
            assert sig == s[i - 1][2]  # next signal is prior exit close


def test_inv_vol_weights_sum_and_cap():
    names = [f"T{i}" for i in range(30)]
    vol = pd.Series({n: 0.10 + i * 0.01 for i, n in enumerate(names)})
    w = weights_inv_vol(names, vol)
    assert abs(sum(w.values()) - 1) < 1e-12
    assert max(w.values()) <= 0.05 + 1e-12


def test_cost_units_initial_and_replacement():
    assert cost_units(set(), {"A", "B"}) == 1.0
    assert cost_units({"A", "B"}, {"A", "C"}) == 1.0  # 50% turnover * 2 sides


def test_metrics_use_period_days():
    periods = [{"net": 0.05, "days": 90, "turnover": 1, "cost": 0, "trades": 1},
               {"net": -0.02, "days": 90, "turnover": 1, "cost": 0, "trades": 1},
               {"net": 0.03, "days": 90, "turnover": 1, "cost": 0, "trades": 1}]
    m = metrics(periods)
    assert m["periods"] == 3
    assert m["cagr"] is not None
    assert m["max_drawdown"] <= 0
