# -*- coding: utf-8 -*-
"""Small deterministic tests for the reused fixed-factor backtest helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import restricted_503_factor_validation as bt  # noqa: E402


def test_bh_is_monotone_and_bounded():
    q = bt.bh([0.01, 0.04, 0.03, 0.20])
    assert q == sorted(q)
    assert all(0 <= x <= 1 for x in q)


def test_metrics_reports_cost_adjusted_values():
    rows = [{"gross": 0.02, "net": 0.019, "turnover": 0.2, "n": 100, "n_long": 20, "n_short": 20},
            {"gross": -0.01, "net": -0.011, "turnover": 0.2, "n": 100, "n_long": 20, "n_short": 20},
            {"gross": 0.01, "net": 0.009, "turnover": 0.2, "n": 100, "n_long": 20, "n_short": 20}]
    out = bt.metrics(rows, "test")
    assert out["n"] == 3
    assert out["net_mean"] < out["gross_mean"]
    assert abs(out["mean_turnover"] - 0.2) < 1e-12
