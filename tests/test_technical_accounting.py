# -*- coding: utf-8 -*-
"""Tests for Phase 2.3 accounting integration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from technical_strategy_backtest import stats  # noqa: E402


def test_stats_use_dates_and_period_returns():
    rows = [
        {"entry_date": "2020-01-02", "exit_date": "2020-02-01", "gross": 0.10},
        {"entry_date": "2020-02-03", "exit_date": "2020-03-02", "gross": -0.05},
        {"entry_date": "2020-03-03", "exit_date": "2020-04-01", "gross": 0.02},
    ]
    out = stats(rows)
    assert out["observations"] == 3
    assert out["cagr"] is not None
    assert out["sharpe"] is not None
    assert out["periods_per_year"] > 0


def test_stats_does_not_use_cagr_over_vol():
    rows = [
        {"entry_date": "2020-01-02", "exit_date": "2020-02-01", "gross": 0.10},
        {"entry_date": "2020-02-03", "exit_date": "2020-03-02", "gross": -0.05},
        {"entry_date": "2020-03-03", "exit_date": "2020-04-01", "gross": 0.02},
    ]
    out = stats(rows)
    assert abs(out["sharpe"] - out["cagr"] / out["annualized_volatility"]) > 1e-6
