#!/usr/bin/env python3
"""Cost sensitivity for the Phase 3.2 risk portfolio only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

from .backtest import SimConfig, risk_alloc, simulate, summarize
from .data import add_features, load_benchmark, load_panel
from .signals import generate_signals


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stocks", required=True); p.add_argument("--etf-dir", required=True)
    p.add_argument("--spy", required=True); p.add_argument("--output", required=True)
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--costs", default="5,10,20,50")
    a = p.parse_args()
    panel = load_panel(Path(a.stocks), Path(a.etf_dir))
    bench = load_benchmark(Path(a.spy))
    sig = generate_signals(add_features(panel, bench), start=a.start, min_assets=100)
    ev = {}
    for dt, g in sig[sig.buy_candidate].groupby("next_trading_date"):
        if pd.notna(dt):
            ev[pd.Timestamp(dt)] = g[["ticker", "score"]].rename(columns={"score": "Score"}).copy()
    allp = pd.concat([panel, bench.assign(asset_class="ETF")], ignore_index=True).drop_duplicates(["Date", "Ticker"])
    opens = allp.pivot_table(index="Date", columns="Ticker", values="Open", aggfunc="last").sort_index()
    raw_closes = allp.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index()
    closes = raw_closes.ffill(limit=5)
    out = {}
    for c in tuple(int(x) for x in a.costs.split(",")):
        cfg = SimConfig(cost_bps=c)
        daily, hard = simulate(opens, closes, ev, lambda x, y, z, cfg=cfg: risk_alloc(x, y, z, closes, cfg), cfg, raw_closes=raw_closes)
        out[str(c)] = summarize(daily, hard, cfg)
    Path(a.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: {"cagr": v["cagr"], "max_drawdown": v["max_drawdown"]} for k, v in out.items()}, indent=2))


if __name__ == "__main__":
    main()
