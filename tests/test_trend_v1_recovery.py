# -*- coding: utf-8 -*-
"""Tests for Phase 3.2.2 recovery and accounting fixes."""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from trend_v1.accounting import annual  # noqa: E402
from trend_v1.backtest import MissingExecutionPriceError, SimConfig, simulate  # noqa: E402
from trend_v1.recovery import RecoveryState  # noqa: E402
from trend_v1.risk import RiskConfig, allocate, capped_weights  # noqa: E402


def test_waterfill_name_cap_across_sizes():
    for n in (1, 2, 5, 10, 50):
        raw = pd.Series(np.linspace(10, 1, n), index=[f"T{i}" for i in range(n)])
        w = capped_weights(raw, 0.10)
        assert w.max() <= 0.10 + 1e-12
        assert w.sum() <= 1.0 + 1e-12


def test_allocate_cap_unequal():
    dates = pd.bdate_range("2020-01-01", periods=90)
    closes = pd.DataFrame({f"T{i}": np.linspace(100, 110 + i, len(dates)) * (1 + 0.02 * i) for i in range(10)}, index=dates)
    cand = pd.DataFrame({"ticker": list(closes.columns), "Score": np.linspace(1, 0.1, 10)})
    w, _ = allocate(cand, closes, dates[-1], 0.0, RiskConfig(max_weight=0.10))
    assert max(w.values()) <= 0.10 + 1e-9
    assert sum(w.values()) <= 1.0 + 1e-9


def test_recovery_needs_two_weeks():
    r = RecoveryState(design="market")
    r.update(0.13, True); assert r.cap == 0 and r.mode == "CASH_DEFENSE"
    r.update(0.13, True); assert r.mode == "RECOVERY" and r.cap == 0.25
    r.update(0.13, True); assert r.cap == 0.50


def test_recovery_immediate_risk_off():
    r = RecoveryState(design="market")
    r.update(0.13, True); r.update(0.13, True)
    assert r.cap == 0.25
    r.update(0.13, False)
    assert r.mode == "CASH_DEFENSE" and r.cap == 0


def test_sticky_never_recovers():
    r = RecoveryState(design="sticky")
    for _ in range(10):
        r.update(0.13, True)
    assert r.cap == 0


def test_breadth_requires_breadth():
    r = RecoveryState(design="market_breadth")
    r.update(0.13, True, False); r.update(0.13, True, False)
    assert r.cap == 0
    r.update(0.13, True, True); r.update(0.13, True, True)
    assert r.mode == "RECOVERY"


def test_missing_open_for_held_raises():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    opens = pd.DataFrame({"A": [100.0, np.nan]}, index=dates)
    closes = pd.DataFrame({"A": [100.0, 101.0]}, index=dates)
    events = {dates[0]: pd.DataFrame({"ticker": ["A"], "Score": [1]}),
              dates[1]: pd.DataFrame({"ticker": ["A"], "Score": [1]})}
    try:
        simulate(opens, closes, events, lambda c, d, dd: ({"A": 1.0}, {"reason": "OK", "defense": "NORMAL"}),
                 SimConfig(cost_bps=0))
    except MissingExecutionPriceError:
        pass
    else:
        raise AssertionError("missing held Open accepted")


def test_annual_uses_prior_year_end_nav():
    dates = pd.to_datetime(["2023-12-29", "2024-01-02", "2024-12-31"])
    daily = pd.DataFrame({"date": dates, "nav": [1.1, 1.1, 1.21]})
    a = annual(daily)
    assert abs(a[0]["return"] - 0.10) < 1e-12
    assert abs(a[1]["return"] - 0.10) < 1e-12


from trend_v1.events import events_from_signals


def test_shared_event_builder_includes_empty_week():
    sig = pd.DataFrame([
        {"signal_date": "2024-01-05", "next_trading_date": "2024-01-08", "ticker": "A", "buy_candidate": True, "score": 1.0},
        {"signal_date": "2024-01-12", "next_trading_date": "2024-01-16", "ticker": "A", "buy_candidate": False, "score": None},
    ])
    ev = events_from_signals(sig)
    assert pd.Timestamp("2024-01-16") in ev
    assert len(ev[pd.Timestamp("2024-01-16")]) == 0
