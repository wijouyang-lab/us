#!/usr/bin/env python3
"""Run one recovery design/cost case (memory-safe)."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from .accounting import annual, metrics
from .backtest import SimConfig, equal_alloc, risk_alloc, simulate, summarize
from .data import add_features, load_benchmark, load_panel
from .events import events_from_signals, spy_trend_events
from .recovery import RecoveryState
from .signals import generate_signals

SPLITS = {"train": ("2018-01-01", "2020-12-31"), "validation": ("2021-01-01", "2023-12-31"),
          "test": ("2024-01-01", "2026-10-28")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stocks", required=True); p.add_argument("--etf-dir", required=True)
    p.add_argument("--spy", required=True); p.add_argument("--output", required=True)
    p.add_argument("--design", choices=["sticky", "market", "market_breadth"], required=True)
    p.add_argument("--cost", type=int, default=10)
    a = p.parse_args()
    panel = load_panel(Path(a.stocks), Path(a.etf_dir)); bench = load_benchmark(Path(a.spy))
    feat = add_features(panel, bench); sig = generate_signals(feat, start="2018-01-01", min_assets=100)
    allp = pd.concat([panel, bench.assign(asset_class="ETF")], ignore_index=True).drop_duplicates(["Date", "Ticker"])
    opens = allp.pivot_table(index="Date", columns="Ticker", values="Open", aggfunc="last").sort_index()
    raw = allp.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index()
    closes = raw.ffill(limit=5)
    ev = events_from_signals(sig)
    sig_by_exec = {}
    for sd, g in sig.groupby("signal_date"):
        nxt = g.next_trading_date.dropna()
        if not nxt.empty:
            sig_by_exec[pd.Timestamp(nxt.iloc[0])] = pd.Timestamp(sd)
    s = bench.sort_values("Date").copy(); s["MA200"] = s.Close.rolling(200, min_periods=200).mean(); s["Slope"] = s.MA200 / s.MA200.shift(20) - 1
    s["ok"] = (s.Close > s.MA200) & (s.Slope > 0); s = s.set_index("Date")
    breadth = feat.groupby("Date").apply(lambda x: float((x.Close > x.MA200).mean()) if x.MA200.notna().any() else np.nan)
    spy_map = {d: bool(s.ok.get(sd, False)) for d, sd in sig_by_exec.items()}
    breadth_map = {d: bool(breadth.get(sd, np.nan) >= 0.5) if pd.notna(breadth.get(sd, np.nan)) else False for d, sd in sig_by_exec.items()}
    cfg = SimConfig(cost_bps=a.cost); rec = RecoveryState(design=a.design)
    daily, hard = simulate(opens, closes, ev, lambda x, y, z: risk_alloc(x, y, z, closes, cfg), cfg,
                           raw_closes=raw, recovery=rec, spy_ok_map=spy_map, breadth_ok_map=breadth_map)
    splits = {}
    for name, (x, y) in SPLITS.items():
        d = daily[(daily.date >= pd.Timestamp(x)) & (daily.date <= pd.Timestamp(y))]
        h = [e for e in hard if pd.Timestamp(e["date"]) >= pd.Timestamp(x) and pd.Timestamp(e["date"]) <= pd.Timestamp(y)]
        splits[name] = summarize(d, h, cfg)
    out = {"design": a.design, "cost_bps": a.cost, "metrics": summarize(daily, hard, cfg),
           "splits": splits, "transitions": rec.transitions, "final_mode": rec.mode}
    Path(a.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"design": a.design, "cost": a.cost, "cagr": out["metrics"]["cagr"],
                      "dd": out["metrics"]["max_drawdown"], "sharpe": out["metrics"]["sharpe"]}, indent=2))


if __name__ == "__main__":
    main()
