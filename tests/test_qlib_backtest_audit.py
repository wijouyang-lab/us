# -*- coding: utf-8 -*-
"""Pure-function checks for the Qlib backtest audit; skips without Qlib."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("qlib")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import audit_qlib_backtest as audit  # noqa: E402


def _records():
    return [
        {"date": "2026-01-31", "gross": 0.02, "turnover": 1.0, "n_all": 100, "n_long": 20, "n_short": 20, "q5": 0.03, "q1": 0.01},
        {"date": "2026-02-28", "gross": 0.01, "turnover": 0.5, "n_all": 100, "n_long": 20, "n_short": 20, "q5": 0.02, "q1": 0.01},
        {"date": "2026-03-31", "gross": -0.01, "turnover": 0.5, "n_all": 100, "n_long": 20, "n_short": 20, "q5": 0.00, "q1": 0.01},
    ]


def test_metrics_use_compounded_annualization_and_one_way_cost():
    m = audit.metrics(_records(), 5.0)
    net = np.array([0.02 - 0.0005, 0.01 - 0.00025, -0.01 - 0.00025])
    expected_ann = np.prod(1 + net) ** (12 / 3) - 1
    assert abs(m["net_mean_monthly"] - net.mean()) < 1e-12
    assert abs(m["ann_return"] - expected_ann) < 1e-12
    assert m["avg_long_names"] == 20 and m["avg_short_names"] == 20
    assert abs(m["mean_cost_monthly"] - (0.0005 + 0.00025 + 0.00025) / 3) < 1e-12


def test_initial_turnover_is_full_open_and_q5_q1_are_legs():
    pred = pd.Series(
        np.linspace(0, 1, 60),
        index=pd.MultiIndex.from_tuples(
            [(pd.Timestamp("2026-01-30"), f"T{i:02d}") for i in range(60)],
            names=["datetime", "instrument"],
        ),
    )
    labels = pd.DataFrame({
        "Date": pd.Timestamp("2026-01-30"),
        "Ticker": [f"T{i:02d}" for i in range(60)],
        "next": np.linspace(-0.01, 0.02, 60),
    })
    rec = audit.monthly_records(pred, labels, [pd.Timestamp("2026-01-30")], (-1, 1))[0]
    assert rec["turnover"] == 1.0
    assert 10 <= rec["n_long"] <= 15
    assert abs(rec["n_long"] - rec["n_short"]) <= 1


def test_market_adjusted_uses_same_dates_and_reports_alpha_ci():
    records = _records() + [
        {"date": "2026-04-30", "gross": 0.015, "turnover": 0.5, "n_all": 100,
         "n_long": 20, "n_short": 20, "q5": 0.02, "q1": 0.005}
    ]
    ew = pd.Series([0.01, 0.02, 0.0, 0.01], index=pd.to_datetime([r["date"] for r in records]))
    out = audit.market_adjusted(records, ew, "gross")
    assert out["status"] == "OK"
    assert out["n"] == 4
    assert "alpha_t" in out and len(out["alpha_ci95"]) == 2
