#!/usr/bin/env python3
"""Post-process factor-validation daily detail into annual/rolling/regime/Q summaries."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd


def main():
    base = Path("data/research/factor_validation")
    d = pd.read_parquet(base / "daily_ic.parquet", columns=["Date", "Horizon", "Factor", "IC", "RankIC", "Q1", "Q2", "Q3", "Q4", "Q5", "Q5_Q1"])
    d["Date"] = pd.to_datetime(d["Date"])
    spy = pd.read_csv("../proxy_data/SPY.csv", usecols=["Date", "Close"])
    spy["Date"] = pd.to_datetime(spy["Date"])
    spy = spy.sort_values("Date")
    spy["MA200"] = spy.Close.rolling(200, min_periods=200).mean()
    spy["Vol20"] = spy.Close.pct_change().rolling(20, min_periods=20).std() * np.sqrt(252)
    spy["Ret200"] = spy.Close / spy.Close.shift(200) - 1
    reg = []
    for dt, g in spy.groupby(spy.Date.dt.date):
        row = g.iloc[-1]
        reg.append({"date": str(dt), "trend": "bull" if row.Close >= row.MA200 else "bear",
                    "vol": "high" if row.Vol20 >= 0.20 else "low",
                    "regime": "trend" if abs(row.Ret200) >= 0.10 else "range"})
    r = pd.DataFrame(reg); r["date"] = pd.to_datetime(r["date"])
    d = d.merge(r, left_on="Date", right_on="date", how="left")
    out = {"rolling_12m": [], "regime": [], "quintiles": []}
    for (h, f), g in d.groupby(["Horizon", "Factor"]):
        g = g.sort_values("Date")
        roll = g["RankIC"].rolling(252, min_periods=252).mean().dropna()
        out["rolling_12m"].append({"Horizon": int(h), "Factor": f, "windows": len(roll),
                                   "positive_window_fraction": float((roll > 0).mean()) if len(roll) else None,
                                   "last": float(roll.iloc[-1]) if len(roll) else None,
                                   "min": float(roll.min()) if len(roll) else None,
                                   "max": float(roll.max()) if len(roll) else None})
        for key in ("trend", "vol", "regime"):
            for val, x in g.groupby(key):
                out["regime"].append({"Horizon": int(h), "Factor": f, "key": key, "value": val,
                                      "dates": len(x), "mean_rank_ic": float(x.RankIC.mean())})
        out["quintiles"].append({"Horizon": int(h), "Factor": f,
                                 "Q1": float(g.Q1.mean()), "Q2": float(g.Q2.mean()),
                                 "Q3": float(g.Q3.mean()), "Q4": float(g.Q4.mean()),
                                 "Q5": float(g.Q5.mean()), "Q5_Q1": float(g.Q5_Q1.mean())})
    (base / "stability.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"rolling": len(out["rolling_12m"]), "regime": len(out["regime"]), "quintiles": len(out["quintiles"])}, indent=2))


if __name__ == "__main__":
    main()
