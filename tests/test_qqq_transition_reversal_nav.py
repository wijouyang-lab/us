# -*- coding: utf-8 -*-
"""Audit tests for QQQ TRANSITION 5-day reversal NAV backtest."""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from qqq_transition_reversal_nav import MissingPriceError, annual, build_panel, simulate  # noqa: E402


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
    daily, trades, skipped, missing, opened, pending = simulate(q, b, s, 1.0, 0, idle="cash")
    assert len(trades) == 1
    assert trades[0].entry == dates[2]
    assert trades[0].exit == dates[7]
    assert daily.in_market.sum() == 5


def test_overlapping_signal_is_skipped():
    dates, q, b, s = frames(signal_at=1)
    q.loc[dates[3], "Signal"] = True
    _, trades, skipped, *_ = simulate(q, b, s, 1.0, 0, idle="cash")
    assert len(trades) == 1 and skipped == 1


def test_cost_models_are_separate_and_charged_once():
    dates, q, b, s = frames()
    _, t_all, *_ = simulate(q, b, s, 1.0, 100, idle="bil", cost_model="all_legs")
    _, t_qqq, *_ = simulate(q, b, s, 1.0, 100, idle="bil", cost_model="qqq_only")
    assert t_all[0].bil_cost > 0
    assert t_qqq[0].bil_cost == 0
    assert t_all[0].qqq_cost > 0
    assert abs(t_all[0].qqq_cost - 0.019701) < 1e-12


def test_bil_idle_earns_return():
    dates, q, b, s = frames()
    b["AdjClose"] = np.linspace(100, 110, len(dates))
    b["AdjOpen"] = b.AdjClose
    q["Signal"] = False
    daily, *_ = simulate(q, b, s, 0.5, 0, idle="bil")
    assert daily.nav.iloc[-1] > 1.0


def test_missing_entry_open_fails_closed():
    dates, q, b, s = frames()
    q.loc[dates[2], "AdjOpen"] = np.nan
    try:
        simulate(q, b, s, 1.0, 0, idle="cash")
    except MissingPriceError:
        pass
    else:
        raise AssertionError("missing entry accepted")


def test_missing_daily_close_fails_closed():
    dates, q, b, s = frames()
    q.loc[dates[4], "AdjClose"] = np.nan
    try:
        simulate(q, b, s, 1.0, 0, idle="cash")
    except MissingPriceError:
        pass
    else:
        raise AssertionError("missing close accepted")


def _regime_panel(spy_path):
    dates = pd.bdate_range("2010-01-01", periods=400)
    q = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    b = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s["Close"] = spy_path
    q["AdjClose"] = np.r_[np.full(399, 100.0), 70.0]
    q2, _, s2 = build_panel(q, b, s)
    return q2, s2


def test_risk_on_and_off_do_not_signal_even_with_crash():
    q_on, _ = _regime_panel(np.linspace(100, 200, 400))
    q_off, _ = _regime_panel(np.linspace(200, 100, 400))
    assert not bool(q_on.Signal.iloc[-1])
    assert not bool(q_off.Signal.iloc[-1])
    assert bool(q_on.Event.iloc[-1])
    assert bool(q_off.Event.iloc[-1])


def test_transition_can_signal():
    s = np.r_[np.linspace(100, 200, 399), 150.0]
    q, spy = _regime_panel(s)
    assert spy.Regime.iloc[-1] == "TRANSITION"
    assert bool(q.Signal.iloc[-1])


def test_threshold_uses_only_past():
    dates = pd.bdate_range("2010-01-01", periods=400)
    q = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": np.linspace(100, 120, 400)}, index=dates)
    b = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s["Close"] = np.linspace(100, 110, 400)
    q1, _, _ = build_panel(q, b, s)
    t1 = q1.Threshold.iloc[350]
    q2 = q.copy(); q2.loc[q2.index > dates[350], "AdjClose"] *= 10
    q3, _, _ = build_panel(q2, b, s)
    assert q3.Threshold.iloc[350] == t1


def test_spy_is_authoritative_calendar():
    dates = pd.bdate_range("2020-01-01", periods=10)
    extra = pd.bdate_range("2020-01-01", periods=11)
    q = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=extra)
    b = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    s = pd.DataFrame({"Open": 100.0, "Close": 100.0, "AdjClose": 100.0}, index=dates)
    q2, b2, _ = build_panel(q, b, s)
    assert q2.index.equals(s.index) and b2.index.equals(s.index)


def test_end_open_trade_and_pending_reported():
    dates = pd.bdate_range("2020-01-01", periods=7)
    q = pd.DataFrame({"AdjOpen": 100.0, "AdjClose": 100.0, "Signal": False, "Event": False}, index=dates)
    q.loc[dates[1], "Signal"] = True
    b = pd.DataFrame({"AdjOpen": 100.0, "AdjClose": 100.0}, index=dates)
    s = pd.DataFrame({"Regime": "TRANSITION"}, index=dates)
    daily, trades, _, _, opened, pending = simulate(q, b, s, 1.0, 0, idle="cash")
    assert opened == 1
    assert trades[0].status == "OPEN"
    assert daily.nav.iloc[-1] > 0


def test_annual_first_base_and_compounding():
    dates = pd.to_datetime(["2007-12-31", "2008-12-31", "2009-12-31"])
    daily = pd.DataFrame({"date": dates, "nav": [1.0, 1.1, 1.21]})
    a = annual(daily)
    assert abs(a[0]["return"] - 0.0) < 1e-12
    assert abs(a[1]["return"] - 0.10) < 1e-12
