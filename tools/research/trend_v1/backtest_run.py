#!/usr/bin/env python3
"""Run Phase 3.2 four-way Trend V1 portfolio comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .accounting import metrics
from .backtest import SimConfig, equal_alloc, risk_alloc, simulate, summarize
from .data import add_features, load_benchmark, load_panel
from .signals import generate_signals


def _events_from_signals(sig):
    ev = {}
    for dt, g in sig[sig.buy_candidate].groupby("next_trading_date"):
        if pd.isna(dt):
            continue
        ev[pd.Timestamp(dt)] = g[["ticker", "score"]].rename(columns={"score": "Score"}).copy()
    return ev


def _spy_trend_events(spy):
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
    return ev


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stocks", required=True)
    p.add_argument("--etf-dir", required=True)
    p.add_argument("--spy", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--daily-out", default=None)
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--skip-sensitivity", action="store_true")
    a = p.parse_args(argv)
    panel = load_panel(Path(a.stocks), Path(a.etf_dir))
    bench = load_benchmark(Path(a.spy))
    feat = add_features(panel, bench)
    sig = generate_signals(feat, start=a.start, min_assets=100)
    # include SPY only for execution/valuation; not a candidate
    allp = pd.concat([panel, bench.assign(asset_class="ETF")], ignore_index=True).drop_duplicates(["Date", "Ticker"])
    opens = allp.pivot_table(index="Date", columns="Ticker", values="Open", aggfunc="last").sort_index()
    closes = allp.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index().ffill()
    events = _events_from_signals(sig)
    ev_equal = events
    ev_risk = events
    spy_events = {k: v for k, v in _spy_trend_events(bench).items() if k >= pd.Timestamp(a.start)}
    first = min(min(events), min(spy_events))
    out = {"label": "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED", "start": a.start,
           "four_way_10bps": {}, "risk_cost_sensitivity": {}}
    # A: SPY buyhold, aligned to the same start date
    spy_close = bench.sort_values("Date").set_index("Date").Close
    spy_close = spy_close[spy_close.index >= pd.Timestamp(a.start)]
    daily_a = pd.DataFrame({"date": spy_close.index, "nav": spy_close / spy_close.iloc[0],
                            "cash": 0.0, "stock": spy_close / spy_close.iloc[0], "cost": 0.0,
                            "buy": 0.0, "sell": 0.0, "expected_vol": None, "clusters": None,
                            "n_holdings": 1, "max_weight": 1.0, "defense": None})
    out["four_way_10bps"]["A_spy_buyhold"] = metrics(daily_a)
    # B: SPY trend
    daily_b, hb = simulate(opens, closes, spy_events, equal_alloc, SimConfig(cost_bps=10))
    out["four_way_10bps"]["B_spy_trend"] = summarize(daily_b, hb, SimConfig(cost_bps=10))
    # C: equal-weight confirmed
    daily_c, hc = simulate(opens, closes, ev_equal, equal_alloc, SimConfig(cost_bps=10))
    out["four_way_10bps"]["C_equal_confirmed"] = summarize(daily_c, hc, SimConfig(cost_bps=10))
    # D: risk engine
    cfg = SimConfig(cost_bps=10)
    daily_d, hd = simulate(opens, closes, ev_risk,
                           lambda c, d, dd: risk_alloc(c, d, dd, closes, cfg), cfg)
    out["four_way_10bps"]["D_risk"] = summarize(daily_d, hd, cfg)
    for c in (() if a.skip_sensitivity else (5, 20, 50)):
        cc = SimConfig(cost_bps=c)
        dd, hh = simulate(opens, closes, ev_risk,
                          lambda x, y, z, cc=cc: risk_alloc(x, y, z, closes, cc), cc)
        out["risk_cost_sensitivity"][str(c)] = summarize(dd, hh, cc)
    if a.daily_out:
        daily_d.to_csv(a.daily_out, index=False)
    Path(a.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["four_way_10bps"], indent=2))


if __name__ == "__main__":
    main()
