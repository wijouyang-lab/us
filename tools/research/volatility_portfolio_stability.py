import json
from pathlib import Path
import numpy as np
import pandas as pd

d = json.load(open("docs/research/volatility_portfolios_phase27_2026-10-30.json"))
spy = pd.read_csv("../proxy_data/SPY.csv", usecols=["Date", "Close"])
spy["Date"] = pd.to_datetime(spy["Date"]); spy = spy.sort_values("Date")
spy["MA200"] = spy.Close.rolling(200, min_periods=200).mean()
spy["Vol20"] = spy.Close.pct_change().rolling(20, min_periods=20).std() * np.sqrt(252)
spy["Ret200"] = spy.Close / spy.Close.shift(200) - 1
reg = {}
for _, r in spy.iterrows():
    reg[r.Date] = {"trend": "bull" if r.Close >= r.MA200 else "bear",
                   "vol": "high" if r.Vol20 >= 0.20 else "low",
                   "regime": "trend" if abs(r.Ret200) >= 0.10 else "range"}
out = {"annual": [], "regime": [], "correlation": {}}
series = {}
for factor, port in d["periods"].items():
    rows = port["equal"]
    series[factor] = pd.Series({r["signal"]: r["gross_q5_q1"] for r in rows})
    df = pd.DataFrame(rows)
    df["year"] = pd.to_datetime(df.signal).dt.year
    for y, g in df.groupby("year"):
        out["annual"].append({"factor": factor, "year": int(y), "periods": len(g),
                              "gross_q5_q1": float(np.prod(1 + g.gross_q5_q1) - 1),
                              "net10_q5_q1": float(np.prod(1 + g["net_10_q5_q1"]) - 1)})
    for r in rows:
        rg = reg.get(pd.Timestamp(r["signal"]))
        if rg:
            out["regime"].append({"factor": factor, **rg, "net_10_q5_q1": r["net_10_q5_q1"]})
for a in series:
    out["correlation"][a] = {}
    for b in series:
        out["correlation"][a][b] = float(series[a].corr(series[b]))
Path("docs/research/volatility_portfolio_stability_2026-10-30.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out["correlation"], indent=2))
print(pd.DataFrame(out["annual"]).to_string(index=False))
