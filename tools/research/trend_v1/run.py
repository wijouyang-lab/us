#!/usr/bin/env python3
"""Run Trend V1 weekly signal research and write coverage/signal summaries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .data import add_features, coverage, load_benchmark, load_panel
from .signals import generate_signals


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stocks", required=True)
    p.add_argument("--etf-dir", required=True)
    p.add_argument("--spy", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--signals-out", default=None)
    p.add_argument("--start", default="2018-01-01")
    a = p.parse_args(argv)
    panel = load_panel(Path(a.stocks), Path(a.etf_dir))
    bench = load_benchmark(Path(a.spy))
    panel = add_features(panel, bench)
    sig = generate_signals(panel, start=a.start, min_assets=100)
    cov = coverage(panel)
    summary = {
        "label": "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED",
        "assets": len(cov), "etfs": sum(x["asset_class"] == "ETF" for x in cov),
        "stocks": sum(x["asset_class"] == "STOCK" for x in cov),
        "weekly_signals": int(sig.signal_date.nunique()) if len(sig) else 0,
        "rows": len(sig),
        "watch_rows": int((sig.state == "WATCH").sum()) if len(sig) else 0,
        "confirmed_rows": int((sig.state == "CONFIRMED").sum()) if len(sig) else 0,
        "buy_candidates": int(sig.buy_candidate.sum()) if len(sig) else 0,
        "exit_signals": int(sig.exit_signal.sum()) if len(sig) else 0,
        "signal_dates": sorted(sig.signal_date.unique().tolist()) if len(sig) else [],
        "coverage": cov,
    }
    Path(a.output).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if a.signals_out:
        sig.to_csv(a.signals_out, index=False)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("coverage", "signal_dates")}, indent=2))


if __name__ == "__main__":
    main()
