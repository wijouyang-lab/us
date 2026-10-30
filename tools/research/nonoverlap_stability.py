import json
from pathlib import Path
import numpy as np
import pandas as pd

d = json.load(open("docs/research/nonoverlap_portfolios_phase274_2026-10-30.json"))
spy = pd.read_csv("../proxy_data/SPY.csv", usecols=["Date", "Close"])
spy["Date"] = pd.to_datetime(spy["Date"]); spy = spy.sort_values("Date")
spy["MA200"] = spy.Close.rolling(200, min_periods=200).mean()
spy["Vol20"] = spy.Close.pct_change().rolling(20, min_periods=20).std() * np.sqrt(252)
spy["Ret200"] = spy.Close / spy.Close.shift(200) - 1
reg = spy[["Date", "Close", "MA200", "Vol20", "Ret200"]].dropna()
reg["trend"] = np.where(reg.Close >= reg.MA200, "bull", "bear")
reg["vol"] = np.where(reg.Vol20 >= 0.20, "high_vol", "low_vol")
reg["regime"] = np.where(reg.Ret200.abs() >= 0.10, "trend", "range")
out = {"annual": [], "regime": []}
for name, ports in d["periods"].items():
    p = ports["10"]
    s = pd.DataFrame(p["equity"], columns=["date", "equity"])
    s["date"] = pd.to_datetime(s.date)
    s = s.drop_duplicates("date").set_index("date").equity
    for y, g in s.groupby(s.index.year):
        out["annual"].append({"strategy": name, "year": int(y), "return": float(g.iloc[-1] / g.iloc[0] - 1), "days": len(g)})
    r = s.pct_change().dropna()
    r = r.to_frame("ret").join(reg.set_index("Date")[["trend", "vol", "regime"]], how="left")
    for key in ("trend", "vol", "regime"):
        for val, x in r.groupby(key):
            out["regime"].append({"strategy": name, "key": key, "value": val, "days": len(x), "mean_daily": float(x.ret.mean()),
                                  "annualized_mean": float(x.ret.mean() * 252), "sharpe": float(x.ret.mean() / x.ret.std(ddof=1) * np.sqrt(252)) if x.ret.std(ddof=1) > 0 else None})
Path("docs/research/nonoverlap_stability_2026-10-30.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(pd.DataFrame(out["annual"]).to_string(index=False))
