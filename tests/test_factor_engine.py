# -*- coding: utf-8 -*-
"""Tests for the unified historical factor engine."""

import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from factor_engine import FACTORS, compute_factors, factor_status  # noqa: E402


def panel(n=300, start="2020-01-01"):
    dates = pd.bdate_range(start, periods=n)
    rows = []
    for i, d in enumerate(dates):
        for t, base in (("AAA", 100.0), ("BBB", 50.0)):
            px = base * (1 + 0.0004 * i)
            rows.append({"Date": d, "Ticker": t, "Open": px, "High": px * 1.01,
                         "Low": px * 0.99, "Close": px, "Volume": 1000 + i})
    return pd.DataFrame(rows)


def spy(n=300):
    dates = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"Date": dates, "Close": 100 * (1 + 0.0002 * np.arange(n))})


def test_ma_and_warmup_status():
    out = compute_factors(panel(), spy())
    a = out[out.Ticker == "AAA"].reset_index(drop=True)
    assert abs(a.loc[19, "MA20"] - a.loc[:19, "Close"].mean()) < 1e-9
    assert pd.isna(a.loc[18, "MA20"])
    assert factor_status(None, 10, 20) == "FACTOR_WARMUP"
    assert factor_status(None, 25, 20) == "MISSING_INPUT"
    assert factor_status(1.0, 25, 20) == "FACTOR_AVAILABLE"


def test_no_ticker_bleed_and_sorted():
    out = compute_factors(panel(), spy())
    for t in ("AAA", "BBB"):
        assert out[out.Ticker == t].Date.is_monotonic_increasing
    assert abs(out[out.Ticker == "AAA"].Close.iloc[0] - 100.0) < 1e-9
    assert abs(out[out.Ticker == "BBB"].Close.iloc[0] - 50.0) < 1e-9


def test_future_price_changes_do_not_change_past_factors():
    p = panel()
    base = compute_factors(p, spy())
    cutoff = p.Date.sort_values().unique()[200]
    q = p.copy()
    q.loc[q.Date > cutoff, ["Open", "High", "Low", "Close"]] *= 1.5
    changed = compute_factors(q, spy())
    left = base[base.Date <= cutoff][["Ticker", "Date"] + FACTORS].reset_index(drop=True)
    right = changed[changed.Date <= cutoff][["Ticker", "Date"] + FACTORS].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_factor_table_has_no_forward_returns():
    out = compute_factors(panel(), spy())
    assert not any("Forward" in c or "Return" in c for c in out.columns)


def test_beta_available_with_spy_alignment():
    out = compute_factors(panel(), spy())
    a = out[out.Ticker == "AAA"]
    assert a["Beta_60D"].notna().any()
    assert a["Stock_RS_20D_vs_SPY"].notna().any()


def test_repeated_run_is_deterministic():
    a = compute_factors(panel(), spy())
    b = compute_factors(panel(), spy())
    pd.testing.assert_frame_equal(a, b)
