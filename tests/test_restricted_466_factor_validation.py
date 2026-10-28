# -*- coding: utf-8 -*-
"""Contract tests for the restricted 466-ticker validation."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import restricted_466_factor_validation as mod  # noqa: E402


def test_metrics_compounding_and_cost_are_explicit():
    rows = [
        {"gross": 0.02, "turnover": 1.0, "cost": 0.0005, "net": 0.0195, "n": 100, "n_long": 20, "n_short": 20},
        {"gross": 0.01, "turnover": 0.5, "cost": 0.00025, "net": 0.00975, "n": 100, "n_long": 20, "n_short": 20},
        {"gross": -0.01, "turnover": 0.5, "cost": 0.00025, "net": -0.01025, "n": 100, "n_long": 20, "n_short": 20},
    ]
    m = mod.metrics(rows, "test")
    expected = np.prod(1 + np.array([r["net"] for r in rows])) ** (12 / 3) - 1
    assert abs(m["ann_return"] - expected) < 1e-12
    assert m["mean_turnover"] == 2 / 3


def test_bh_q_values_are_monotone():
    p = [0.01, 0.04, 0.03, 0.2, 0.9]
    q = mod.bh(p)
    assert all(0 <= x <= 1 for x in q)
    paired = sorted(zip(p, q))
    assert all(paired[i][1] <= paired[i + 1][1] + 1e-12 for i in range(len(paired) - 1))


def test_complete_ticker_filter_and_labels(tmp_path):
    dates = pd.bdate_range("2020-01-02", periods=80)
    rows = []
    for ticker in ("AAA", "BBB"):
        for d in dates:
            rows.append({"Date": d.date().isoformat(), "Ticker": ticker, "High": 11,
                         "Low": 9, "Close": 10, "Volume": 1_000_000})
    path = tmp_path / "price.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    df = mod.load_panel(path)
    assert df["Ticker"].nunique() == 2
    assert df["Date"].nunique() == 80
    assert "NOT A FULL PIT RESULT" in mod.LABEL
