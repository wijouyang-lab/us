# -*- coding: utf-8 -*-
"""Trend V1 state, scoring and calendar tests."""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from trend_v1.data import add_features, load_benchmark, latest_snapshot  # noqa: E402
from trend_v1.scoring import score_snapshot  # noqa: E402
from trend_v1.state import TrendState, evaluate_row  # noqa: E402
from trend_v1.signals import generate_signals, weekly_dates  # noqa: E402


def row(**kw):
    base = dict(Close=110.0, MA50=100.0, MA200=90.0, MA200_Slope20=0.01, Mom20=0.05, Rel20=0.02)
    base.update(kw)
    return base


def test_watch_does_not_buy():
    st, info = evaluate_row(row(), TrendState())
    assert info["state"] == "WATCH"
    assert info["confirmed"] is False


def test_two_week_confirmation():
    st, info = evaluate_row(row(), TrendState())
    st, info = evaluate_row(row(), st)
    assert info["state"] == "CONFIRMED"


def test_exit_and_reentry_reset():
    st = TrendState("CONFIRMED")
    st, info = evaluate_row(row(Close=80.0, MA200=90.0), st)
    assert info["exit_signal"] is True
    assert st.state == "FLAT"
    st, info = evaluate_row(row(), st)
    assert info["state"] == "WATCH"
    assert info["confirmed"] is False


def test_missing_data_fails_closed():
    st, info = evaluate_row({"Close": 100.0}, TrendState())
    assert info["state"] == "FLAT"
    assert info["confirmed"] is False


def test_etf_and_stock_share_one_rank_pool():
    snap = pd.DataFrame([
        {"Ticker": "QQQ", "asset_class": "ETF", "Close": 110, "MA50": 100, "MA200": 90,
         "MA200_Slope20": .01, "Mom20": .1, "Mom60": .2, "Mom120": .3, "Vol60": .2, "DD60": -.1, "RiskEff20": .5,
         "Rel20": .05, "Rel60": .1, "Rel120": .2},
        {"Ticker": "AAA", "asset_class": "STOCK", "Close": 100, "MA50": 95, "MA200": 90,
         "MA200_Slope20": .01, "Mom20": .05, "Mom60": .1, "Mom120": .2, "Vol60": .3, "DD60": -.2, "RiskEff20": .2,
         "Rel20": .02, "Rel60": .05, "Rel120": .1},
    ])
    out = score_snapshot(snap)
    assert set(out.Ticker) == {"QQQ", "AAA"}
    assert out.Score.notna().all()


def test_no_fixed_holding_cap():
    snap = pd.DataFrame([{
        "Ticker": f"T{i}", "asset_class": "STOCK", "Close": 100 + i, "MA50": 95, "MA200": 90,
        "MA200_Slope20": .01, "Mom20": .01 * i, "Mom60": .1, "Mom120": .2, "Vol60": .2,
        "DD60": -.1, "RiskEff20": .1 * i, "Rel20": .01, "Rel60": .05, "Rel120": .1} for i in range(1, 9)])
    out = score_snapshot(snap)
    assert len(out[out.Score.notna()]) == 8


def test_weekly_calendar_and_holiday():
    dates = [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-04"), pd.Timestamp("2024-01-05"),
             pd.Timestamp("2024-01-08"), pd.Timestamp("2024-01-11"), pd.Timestamp("2024-01-16")]
    assert weekly_dates(dates) == [pd.Timestamp("2024-01-05"), pd.Timestamp("2024-01-11"), pd.Timestamp("2024-01-16")]


def test_future_mutation_does_not_change_past_score():
    dates = pd.bdate_range("2020-01-01", periods=300)
    frames = []
    for t, cls, base in (("SPY", "ETF", 100), ("AAA", "STOCK", 50), ("QQQ", "ETF", 80)):
        frames.append(pd.DataFrame({"Date": dates, "Ticker": t, "asset_class": cls,
                                    "Open": base, "High": base, "Low": base,
                                    "Close": np.linspace(base, base * 1.5, len(dates)), "Volume": 1e6}))
    d = pd.concat(frames)
    b = d[d.Ticker.eq("SPY")][["Date", "Ticker", "Open", "Close", "asset_class"]]
    f = add_features(d, b)
    snap = latest_snapshot(f, dates[240])
    a = score_snapshot(snap)[["Ticker", "Score"]].sort_values("Ticker").reset_index(drop=True)
    d2 = d.copy()
    d2.loc[d2.Date > dates[240], "Close"] *= 10
    f2 = add_features(d2, b)
    b2 = score_snapshot(latest_snapshot(f2, dates[240]))[["Ticker", "Score"]].sort_values("Ticker").reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b2)


def test_deterministic_signal_rows():
    dates = pd.bdate_range("2020-01-01", periods=300)
    frames = []
    for t, cls, base in (("SPY", "ETF", 100), ("AAA", "STOCK", 50)):
        frames.append(pd.DataFrame({"Date": dates, "Ticker": t, "asset_class": cls,
                                    "Open": base, "High": base, "Low": base,
                                    "Close": np.linspace(base, base * 1.5, len(dates)), "Volume": 1e6}))
    d = pd.concat(frames)
    b = d[d.Ticker.eq("SPY")][["Date", "Ticker", "Open", "Close", "asset_class"]]
    f = add_features(d, b)
    s1 = generate_signals(f, start="2021-01-01")
    s2 = generate_signals(f, start="2021-01-01")
    pd.testing.assert_frame_equal(s1, s2)


def test_signal_and_entry_dates_are_separate():
    dates = pd.bdate_range("2020-01-01", periods=300)
    frames = []
    for t, cls, base in (("SPY", "ETF", 100), ("AAA", "STOCK", 50)):
        frames.append(pd.DataFrame({"Date": dates, "Ticker": t, "asset_class": cls,
                                    "Open": base, "High": base, "Low": base,
                                    "Close": np.linspace(base, base * 1.5, len(dates)), "Volume": 1e6}))
    d = pd.concat(frames)
    b = d[d.Ticker.eq("SPY")][["Date", "Ticker", "Open", "Close", "asset_class"]]
    sig = generate_signals(add_features(d, b), start="2021-01-01")
    assert len(sig) > 0
    valid = sig.dropna(subset=["next_trading_date"])
    assert (pd.to_datetime(valid.next_trading_date) > pd.to_datetime(valid.signal_date)).all()
