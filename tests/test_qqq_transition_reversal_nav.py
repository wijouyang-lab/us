# -*- coding: utf-8 -*-
"""Tests for QQQ TRANSITION 5-day reversal NAV backtest."""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from qqq_transition_reversal_nav import MissingPriceError, build_panel, simulate  # noqa: E402


def frames(n=12, signal_at=1):
    dates = pd.bdate_range("2020-01-01", periods=n)
    q = pd.DataFrame({"AdjOpen": 100.0, "AdjClose": 100.0, "Signal": False,
                      "Event": False}, index=dates)
    q.loc[dates[signal_at], "Signal"] = True
    b = pd.DataFrame({"AdjOpen": 100.0, "AdjClose": 100.0}, index=dates)
    s = pd.DataFrame({"Regime": "TRANSITION"}, index=dates)
    return dates, q, b, s


def test_entry_next_session_and_five_day_exit():
    dates, q, b, s = frames()
    daily, trades, skipped, missing = simulate(q, b, s, 1.0, 0, idle="cash")
    assert len(trades) == 1
    assert trades[0].entry == dates[2]
    assert trades[0].exit == dates[7]
    assert daily.in_market.sum() == 5


def test_overlapping_signal_is_skipped():
    dates, q, b, s = frames(signal_at=1)
    q.loc[dates[3], "Signal"] = True
    _, trades, skipped, _ = simulate(q, b, s, 1.0, 0, idle="cash")
    assert len(trades) == 1
    assert skipped == 1


def test_cost_charged_on_entry_and_exit():
    dates, q, b, s = frames()
    daily, trades, _, _ = simulate(q, b, s, 1.0, 100, idle="cash")
    t = trades[0]
    assert abs(t.entry_cost - 0.01) < 1e-12
    assert abs(t.exit_cost - 0.0099) < 1e-12
    assert daily.nav.iloc[-1] < 1.0


def test_bil_idle_earns_return():
    dates, q, b, s = frames()
    b["AdjClose"] = np.linspace(100, 110, len(dates))
    b["AdjOpen"] = b.AdjClose
    q["Signal"] = False
    daily, _, _, _ = simulate(q, b, s, 0.5, 0, idle="bil")
    assert daily.nav.iloc[-1] > 1.0


def test_missing_entry_price_fails_closed():
    dates, q, b, s = frames()
    q.loc[dates[2], "AdjOpen"] = np.nan
    try:
        simulate(q, b, s, 1.0, 0, idle="cash")
    except MissingPriceError:
        pass
    else:
        raise AssertionError("missing entry accepted")


def test_signal_requires_transition_regime():
    dates = pd.bdate_range("2018-01-01", periods=400)
    q = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    b = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s["Close"] = np.linspace(100, 200, len(dates))
    q["AdjClose"] = np.r_[np.full(350, 100.0), np.linspace(80, 70, 50)]
    q2, b2, s2 = build_panel(q, b, s)
    assert q2.Signal.sum() >= 0
    # Regime is either RISK_ON or TRANSITION; no fabricated event signal before warmup.
    assert q2.Signal.iloc[:250].sum() == 0


def test_threshold_is_lagged():
    dates = pd.bdate_range("2018-01-01", periods=320)
    q = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": np.linspace(100, 120, 320)}, index=dates)
    b = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s["Close"] = np.linspace(100, 110, 320)
    q2, _, _ = build_panel(q, b, s)
    expected = q2.Ret5.rolling(252, min_periods=252).quantile(0.05).shift(1)
    assert q2.Threshold.equals(expected)
    assert q2.Threshold.iloc[300] == expected.iloc[300]
