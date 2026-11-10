# -*- coding: utf-8 -*-
"""Deterministic tests for shared portfolio accounting."""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from portfolio_accounting import (  # noqa: E402
    cagr, capital_return, cost_units, long_net, long_short_net,
    max_drawdown, sharpe, short_net,
)


def test_long_direction():
    assert abs(long_net(0.10, 0.01) - 0.09) < 1e-12


def test_short_direction_and_cost():
    assert abs(short_net(0.05, 0.01) + 0.06) < 1e-12


def test_long_short_combination():
    assert abs(long_short_net(0.09, -0.06) - 0.03) < 1e-12


def test_one_x_and_two_x_capital():
    assert capital_return(0.03, 1) == 0.03
    assert capital_return(0.03, 2) == 0.015


def test_initial_cost_once_and_zero_turnover():
    assert cost_units(set(), {"A"}, initial=True) == 1.0
    assert cost_units({"A"}, {"A"}, initial=False) == 0.0


def test_buy_and_sell_cost_turnover():
    assert cost_units({"A", "B"}, {"A", "C"}, initial=False) == 1.0


def test_more_cost_lowers_legs():
    assert long_net(0.1, 0.001) > long_net(0.1, 0.005)
    assert short_net(0.05, 0.001) > short_net(0.05, 0.005)


def test_zero_cost_equals_gross():
    assert long_net(0.1, 0.0) == 0.1
    assert short_net(0.1, 0.0) == -0.1


def test_sharpe_uses_period_returns():
    r = [0.01, -0.01, 0.02, 0.0]
    expected = np.mean(r) / np.std(r, ddof=1) * np.sqrt(12)
    assert abs(sharpe(r, 12) - expected) < 1e-12


def test_cagr_uses_actual_years():
    assert abs(cagr([0.10], 1.0) - 0.10) < 1e-12
    assert abs(cagr([0.10], 2.0) - (1.1 ** 0.5 - 1)) < 1e-12


def test_drawdown_uses_equity_curve():
    assert max_drawdown([0.1, -0.2, 0.05]) < 0
    assert max_drawdown([0.1, 0.1]) == 0


def test_repeatable():
    assert capital_return(0.03, 2) == capital_return(0.03, 2)


def test_rejects_nan_and_loss_below_minus_one():
    for bad in ([0.01, float("nan")], [0.01, -1.0]):
        try:
            cagr(bad, 1.0)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid returns accepted")


def test_zero_vol_sharpe_is_none():
    assert sharpe([0.01, 0.01, 0.01], 12) is None
