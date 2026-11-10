# -*- coding: utf-8 -*-
"""Tests for walk-forward metric/regime helpers."""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from walkforward_validation import metrics, regime_at  # noqa: E402


def test_metrics_are_monthly_and_bounded():
    out = metrics([0.01, 0.02, -0.01, 0.0])
    assert out["observations"] == 4
    assert out["cagr"] > 0
    assert out["max_drawdown"] <= 0


def test_regime_uses_current_and_past_values_only():
    spy = pd.DataFrame({
        "Date": pd.bdate_range("2024-01-01", periods=220),
        "Close": list(range(100, 320)),
    })
    spy["MA200"] = spy.Close.rolling(200, min_periods=200).mean()
    spy["Vol20"] = 0.10
    spy["Ret200"] = spy.Close / spy.Close.shift(200) - 1
    out = regime_at(spy, spy.Date.iloc[-1])
    assert out["trend"] == "bull"
    assert out["vol"] == "low_vol"
    assert out["regime"] == "trend"
