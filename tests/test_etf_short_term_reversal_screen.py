from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "research"))

from etf_short_term_reversal_screen import (
    _make_series,
    benjamini_hochberg,
    build_etf_screen,
    hac_dummy_effect,
)


def make_panel(n=650, seed=7, symbol="ETF"):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2019-01-02", periods=n)
    returns = rng.normal(0.0002, 0.006, n)
    close = 100 * np.cumprod(1 + returns)
    open_ = close * (1 + rng.normal(0.0, 0.001, n))
    if symbol == "ETF":
        close[420:] *= 0.90
        open_[420:] *= 0.90
        close[425:] *= 1.12
        open_[425:] *= 1.12
    frame = pd.DataFrame({
        "Date": dates,
        "Ticker": symbol,
        "Open": open_,
        "High": np.maximum(open_, close) * 1.002,
        "Low": np.minimum(open_, close) * 0.998,
        "Close": close,
        "Adj Close": close * 0.999,
        "Volume": np.full(n, 500_000),
        "Dividends": np.zeros(n),
        "Stock Splits": np.zeros(n),
    })
    return frame


def test_threshold_is_lagged_and_does_not_use_future_returns():
    frame = make_panel(symbol="QQQ")
    dates = pd.DatetimeIndex(frame.Date)
    before = _make_series(frame, dates)
    target = dates[400]
    changed = frame.copy()
    changed.loc[changed.Date > target, ["Close", "Adj Close"]] *= 0.5
    after = _make_series(changed, dates)
    assert before.loc[target, "TailThreshold"] == pytest.approx(after.loc[target, "TailThreshold"])
    assert before.loc[target, "Event"] == after.loc[target, "Event"]


def test_hac_dummy_effect_detects_known_event_mean_difference():
    rng = np.random.default_rng(11)
    n = 800
    event = np.zeros(n, dtype=bool)
    event[::20] = True
    returns = rng.normal(0.0, 0.01, n)
    returns[event] += 0.01
    result = hac_dummy_effect(returns, event, max_lag=20)
    assert result["status"] == "DESCRIPTIVE_HAC_OLS"
    assert result["effect"] > 0.007
    assert result["se_hac"] > 0
    assert result["ci95_low"] < result["effect"] < result["ci95_high"]


def test_build_etf_screen_keeps_assets_separate_and_reports_nonoverlap():
    spy = make_panel(symbol="SPY")
    bil = make_panel(symbol="BIL", seed=8)
    gld = make_panel(symbol="GLD", seed=9)
    result = build_etf_screen({"BIL": bil, "GLD": gld}, spy)
    assert result["status"] == "EXPLORATORY_ETF_TIME_SERIES_EVENT_STUDY"
    assert set(result["results"]) == {"BIL", "GLD"}
    for ticker in ("BIL", "GLD"):
        for horizon in ("1", "3", "5"):
            cell = result["results"][ticker]["horizons"][horizon]
            assert cell["n_events"] > 0
            assert 0 <= cell["n_non_overlapping_events"] <= cell["n_events"]
            assert "cost_sensitivity" in cell
            assert set(cell["cost_sensitivity"]) == {"5", "10", "20", "50"}


def test_duplicate_etf_dates_fail_closed():
    frame = make_panel(symbol="BIL")
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate dates"):
        _make_series(frame, pd.DatetimeIndex(make_panel(symbol="SPY").Date))


def test_missing_bil_reference_fails_closed():
    spy = make_panel(symbol="SPY")
    gld = make_panel(symbol="GLD")
    with pytest.raises(ValueError, match="BIL is required"):
        build_etf_screen({"GLD": gld}, spy)


def test_benjamini_hochberg_returns_bounded_monotone_adjustments():
    adjusted = benjamini_hochberg({"a": 0.001, "b": 0.02, "c": 0.04, "d": None})
    assert adjusted["a"] == pytest.approx(0.003)
    assert adjusted["b"] == pytest.approx(0.04)
    assert adjusted["c"] == pytest.approx(0.04)
    assert adjusted["d"] is None
    assert 0 <= adjusted["a"] <= adjusted["b"] <= adjusted["c"] <= 1
