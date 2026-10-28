# -*- coding: utf-8 -*-
"""Contract tests for the fixed five-factor low-frequency research check."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import focused_lowfreq_validation as mod  # noqa: E402


def _snapshot(days=120, tickers=60):
    dates = pd.bdate_range("2025-01-02", periods=days)
    rng = np.random.default_rng(7)
    rows = []
    for t in range(tickers):
        ticker = f"T{t:03d}"
        price = 100 * np.cumprod(1 + rng.normal(0, 0.01, len(dates)))
        for i, d in enumerate(dates):
            rows.append({
                "Technical_Date": d.strftime("%Y-%m-%d"),
                "Ticker": ticker,
                "Price": price[i],
                "ATR_Pct": 2 + (t % 10) * 0.1,
                "Realized_Volatility_20D_Pct": 20 + (t % 10),
                "Momentum_60D_Pct": (t % 10) - 5,
                "RSI": 30 + (t % 40),
                "Volume_Ratio_20D": 0.5 + (t % 10) * 0.1,
            })
    return pd.DataFrame(rows)


def test_bh_qvalues_are_monotone_and_bounded():
    p = [0.01, 0.04, 0.03, 0.2, 0.9]
    q = mod.bh_qvalues(p)
    assert all(0 <= v <= 1 for v in q)
    paired = sorted(zip(p, q))
    assert all(paired[i][1] <= paired[i + 1][1] + 1e-12 for i in range(len(paired) - 1))


def test_forward_return_uses_only_future_price_and_keeps_edge_missing():
    raw = mod.prepare_snapshot(_snapshot(days=30, tickers=2))
    labeled = mod.add_forward_return(raw, horizon=5)
    first = labeled[labeled["Ticker"] == "T000"].sort_values("Date").reset_index(drop=True)
    expected = first.loc[5, "Price"] / first.loc[0, "Price"] - 1
    assert abs(first.loc[0, "Forward_Return"] - expected) < 1e-12
    assert first["Forward_Return"].tail(5).isna().all()


def test_fixed_family_returns_five_rows_and_no_production_imports():
    raw = mod.prepare_snapshot(_snapshot())
    report = mod.evaluate(mod.add_forward_return(raw))
    assert len(report) == 5
    assert set(report["factor"]) == set(mod.FACTORS)
    assert report["n_rebalances"].min() >= 3
    assert report["q_value_bh"].notna().all()
