from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "research"))

from short_term_reversal_screen import (
    benjamini_hochberg,
    build_event_rows,
    classify_market_regime,
    hac_mean_test,
    summarize_cell,
)


def make_prices(n_days: int = 275):
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    idx = np.arange(n_days, dtype=float)
    spy_close = 100.0 + 0.10 * idx
    spy = pd.DataFrame({
        "Date": dates,
        "Open": spy_close - 0.03,
        "Close": spy_close,
    })
    rows = []
    for ticker, slope in (("A", 0.02), ("B", 0.30)):
        close = 100.0 + slope * idx
        volume = np.full(n_days, 100_000.0)
        for i, date in enumerate(dates):
            rows.append({
                "Date": date, "Ticker": ticker,
                "Open": close[i] + 0.02, "Close": close[i], "Volume": volume[i],
            })
    return pd.DataFrame(rows), spy, dates


def test_market_regime_uses_only_information_available_on_that_date():
    _, spy, dates = make_prices()
    before = classify_market_regime(spy)
    target = dates[230]
    changed = spy.copy()
    changed.loc[changed.Date > target, "Close"] *= 0.5
    after = classify_market_regime(changed)
    assert before.loc[target, "Regime"] == "RISK_ON"
    assert after.loc[target, "Regime"] == before.loc[target, "Regime"]
    assert after.loc[target, "MA200"] == pytest.approx(before.loc[target, "MA200"])


def test_relative_reversal_selects_the_weaker_stock_and_uses_exact_calendar_exit():
    stocks, spy, dates = make_prices()
    target = dates[230]
    events, audit = build_event_rows(
        stocks, spy, horizons=(3,), min_names=2, top_fraction=0.5,
        min_price=1.0, min_dollar_volume_20d=0.0, start="2020-01-01",
    )
    row = events[(events.signal_date == target) & (events.horizon == 3)].iloc[0]
    assert row.regime == "RISK_ON"
    assert row.selected_names == 1
    assert row.entry_date == dates[231]
    assert row.exit_date == dates[234]
    assert audit["usable_events_by_horizon"]["3"] > 0


def test_missing_selected_open_rejects_event_instead_of_using_next_available_row():
    stocks, spy, dates = make_prices()
    target = dates[230]
    # A is the selected weak name at target. Remove its exact next-session row.
    stocks = stocks[~((stocks.Ticker == "A") & (stocks.Date == dates[231]))].copy()
    events, audit = build_event_rows(
        stocks, spy, horizons=(3,), min_names=2, top_fraction=0.5,
        min_price=1.0, min_dollar_volume_20d=0.0, start="2020-01-01",
    )
    assert not ((events.signal_date == target) & (events.horizon == 3)).any()
    assert audit["missing_selected_execution_events"] > 0


def test_duplicate_ticker_session_fails_closed():
    stocks, spy, _ = make_prices()
    duplicate = pd.concat([stocks, stocks.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate session keys"):
        build_event_rows(
            duplicate, spy, horizons=(3,), min_names=2, top_fraction=0.5,
            min_price=1.0, min_dollar_volume_20d=0.0,
        )


def test_hac_mean_test_reports_lag_robust_standard_error():
    values = np.array([0.01, -0.004, 0.012, 0.003, -0.002, 0.009,
                       0.005, -0.001, 0.011, 0.004, 0.007, -0.003])
    result = hac_mean_test(values, max_lag=2)
    assert result["n"] == len(values)
    assert result["se_hac"] is not None and result["se_hac"] > 0
    assert result["ci95_low"] < result["mean"] < result["ci95_high"]


def test_benjamini_hochberg_adjustment_is_monotonic_and_bounded():
    adjusted = benjamini_hochberg({"a": 0.01, "b": 0.03, "c": 0.04, "d": None})
    assert adjusted["a"] == pytest.approx(0.03)
    assert adjusted["b"] == pytest.approx(0.04)
    assert adjusted["c"] == pytest.approx(0.04)
    assert adjusted["d"] is None
    assert all(0 <= v <= 1 for v in [adjusted["a"], adjusted["b"], adjusted["c"]])


def test_hac_returns_insufficient_evidence_for_small_sample():
    result = hac_mean_test([0.01, 0.02, -0.01], max_lag=2)
    assert result["n"] == 3
    assert result["se_hac"] is None
    assert result["p_two_sided_normal"] is None



def test_summary_reports_median_excess_and_non_overlapping_event_count():
    events = pd.DataFrame({
        "signal_session_index": [10, 11, 13, 16],
        "horizon": [3, 3, 3, 3],
        "gross_return": [0.04, -0.01, 0.03, 0.02],
        "equal_weight_return": [0.01, 0.00, 0.01, 0.01],
        "spy_return": [0.005, 0.002, 0.003, 0.001],
    })
    result = summarize_cell(events, cost_bps=0)
    assert result["n_events"] == 4
    assert result["n_non_overlapping_events"] == 3
    assert result["median_net_excess_vs_equal_weight_pct"] == pytest.approx(1.5)
    assert result["median_net_excess_vs_spy_pct"] == pytest.approx(2.35)
