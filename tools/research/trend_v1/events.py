"""Shared weekly execution-event construction for all Phase 3 backtests."""
from __future__ import annotations

import pandas as pd


def events_from_signals(sig):
    """Emit one event per signal week, including empty candidate frames."""
    ev = {}
    for _, g in sig.groupby("signal_date"):
        nxt = g.next_trading_date.dropna()
        if nxt.empty:
            continue
        cand = g[g.buy_candidate][["ticker", "score"]].rename(columns={"score": "Score"}).copy()
        ev[pd.Timestamp(nxt.iloc[0])] = cand
    return ev


def spy_trend_events(spy):
    s = spy.sort_values("Date").copy()
    s["MA200"] = s.Close.rolling(200, min_periods=200).mean()
    s["Slope"] = s.MA200 / s.MA200.shift(20) - 1
    weekly = s.groupby(s.Date.dt.to_period("W-FRI")).tail(1)
    cal = s.Date.tolist()
    ev = {}
    for _, r in weekly.iterrows():
        nxt = next((x for x in cal if x > r.Date), None)
        if nxt is None:
            continue
        if r.Close > r.MA200 and r.Slope > 0:
            ev[nxt] = pd.DataFrame({"ticker": ["SPY"], "Score": [1.0]})
        else:
            ev[nxt] = pd.DataFrame(columns=["ticker", "Score"])
    return ev
