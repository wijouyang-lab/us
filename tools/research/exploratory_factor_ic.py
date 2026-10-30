#!/usr/bin/env python3
"""Exploratory 5D/10D factor IC on current-universe snapshots.

Label: EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED.
Not PIT, not strategy Sharpe, not rankable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

LABEL = "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED"
FACTORS = ["Momentum_5D_Pct", "Momentum_20D_Pct", "RSI_14", "Bias_Pct",
           "ATR_Pct", "MA20_Slope_5D", "Realized_Volatility_20D_Pct", "Quant_Score"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--forward-returns", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    snap = pd.read_csv(args.snapshot, low_memory=False)
    fwd = pd.read_csv(args.forward_returns, low_memory=False)
    snap["Signal_Date"] = pd.to_datetime(snap["Technical_Date"], errors="coerce")
    fwd["Signal_Date"] = pd.to_datetime(fwd["Signal_Date"], errors="coerce")
    out = {"label": LABEL, "horizons": {}, "sample": {}}
    for h in (5, 10):
        rows = []
        f = fwd[(fwd.Horizon == h) & (fwd.Sample_Status == "MATURED")]
        m = snap.merge(f[["Signal_Date", "Ticker", "Forward_Return"]], on=["Signal_Date", "Ticker"], how="inner")
        for factor in FACTORS:
            if factor not in m:
                continue
            per_date = []
            for dt, g in m.groupby("Signal_Date"):
                g = g[[factor, "Forward_Return"]].apply(pd.to_numeric, errors="coerce").dropna()
                if len(g) < 20 or g[factor].nunique() < 3:
                    continue
                ic = g[factor].corr(g["Forward_Return"], method="spearman")
                per_date.append((dt, len(g), float(ic)))
            if per_date:
                ics = [x[2] for x in per_date]
                rows.append({"factor": factor, "horizon": h, "dates": len(per_date),
                             "mean_rank_ic": sum(ics) / len(ics),
                             "positive_date_fraction": sum(x > 0 for x in ics) / len(ics),
                             "mean_names": sum(x[1] for x in per_date) / len(per_date),
                             "min_names": min(x[1] for x in per_date)})
        out["horizons"][str(h)] = rows
    Path(args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
