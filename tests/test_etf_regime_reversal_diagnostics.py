from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "research"))

from etf_regime_reversal_diagnostics import (
    _bh_adjust,
    _hac_regime_event_effects,
    _non_overlapping_count,
    run_regime_diagnostics,
)


def test_non_overlapping_event_counter_uses_touching_exit_entry_as_contiguous():
    assert _non_overlapping_count([10, 11, 13, 16, 20], horizon=3) == 4
    assert _non_overlapping_count([], horizon=5) == 0


def test_regime_hac_model_controls_regime_baselines_and_detects_targeted_event_effect():
    rng = np.random.default_rng(1234)
    n = 6000
    regimes = np.resize(np.array(["RISK_ON", "RISK_OFF", "TRANSITION"]), n)
    rng.shuffle(regimes)
    event = rng.random(n) < 0.06
    baseline = np.select(
        [regimes == "RISK_ON", regimes == "RISK_OFF"],
        [0.0008, -0.0012],
        default=0.0001,
    )
    returns = baseline + rng.normal(0.0, 0.008, n)
    returns += (event & (regimes == "TRANSITION")) * 0.004
    result = _hac_regime_event_effects(returns, event, regimes, max_lag=20)
    assert result["TRANSITION"]["effect"] > 0.002
    assert result["TRANSITION"]["t_hac"] > 2
    assert result["TRANSITION"]["p_two_sided_normal"] < 0.05
    assert abs(result["RISK_ON"]["effect"]) < 0.002
    assert abs(result["RISK_OFF"]["effect"]) < 0.002


def test_bh_adjustment_is_monotone_and_bounded():
    adjusted = _bh_adjust({"a": 0.001, "b": 0.02, "c": 0.04, "d": None})
    assert adjusted["a"] == pytest.approx(0.003)
    assert adjusted["b"] == pytest.approx(0.03)
    assert adjusted["c"] == pytest.approx(0.04)
    assert adjusted["d"] is None
    assert 0 <= adjusted["a"] <= adjusted["b"] <= adjusted["c"] <= 1


def make_prices(n: int, ticker: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2019-01-02", periods=n)
    returns = rng.normal(0.0002, 0.008, n)
    if ticker == "SPY":
        returns += 0.0002
    if ticker == "QQQ":
        # Fixed episodic sell-offs and recoveries create reproducible tail events.
        for start in range(300, n - 8, 90):
            returns[start:start + 5] -= 0.035
            returns[start + 5:start + 8] += 0.025
    close = 100.0 * np.cumprod(1.0 + returns)
    open_ = close * (1.0 + rng.normal(0.0, 0.0005, n))
    adj_close = close.copy()
    if ticker == "BIL":
        adj_close = 100.0 * np.cumprod(1.0 + np.full(n, 0.00008))
        close = adj_close.copy()
        open_ = close.copy()
    return pd.DataFrame({
        "Date": dates,
        "Open": open_,
        "High": np.maximum(open_, close) * 1.002,
        "Low": np.minimum(open_, close) * 0.998,
        "Close": close,
        "Adj Close": adj_close,
    })


def test_run_regime_diagnostics_keeps_etfs_separate_and_reports_regime_costs():
    n = 900
    spy = make_prices(n, "SPY", 1)
    bil = make_prices(n, "BIL", 2)
    qqq = make_prices(n, "QQQ", 3)
    result = run_regime_diagnostics({"BIL": bil, "QQQ": qqq}, spy)
    assert result["status"] == "EXPLORATORY_REGIME_CONDITIONED_ETF_REVERSAL"
    assert set(result["results"]) == {"BIL", "QQQ"}
    assert len(result["qqq_period_sensitivity_posthoc"]) == 4 * 3 * 3
    for ticker in ("BIL", "QQQ"):
        for horizon in ("1", "3", "5"):
            cell = result["results"][ticker]["horizons"][horizon]
            assert set(cell["regimes"]) == {"RISK_ON", "RISK_OFF", "TRANSITION"}
            for regime, summary in cell["regimes"].items():
                assert 0 <= summary["n_non_overlapping_events"] <= summary["n_events"]
                assert set(summary["cost_sensitivity"]) == {"5", "10", "20", "50"}
                assert "event_effect_vs_non_event_total_return" in summary
    assert result["multiple_testing"]["not_confirmatory"] is True


def test_duplicate_etf_dates_fail_closed():
    frame = make_prices(500, "BIL", 11)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate dates"):
        run_regime_diagnostics(
            {"BIL": frame, "QQQ": make_prices(500, "QQQ", 12)},
            make_prices(500, "SPY", 13),
        )
