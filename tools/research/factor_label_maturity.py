import json
from pathlib import Path
import numpy as np
import pandas as pd
from tools.research.forward_return import build_forward_returns

f = pd.read_parquet("data/research/factor_snapshots/factors_10y_2026-10-30.parquet", columns=["Ticker", "Date"])
f["Date"] = pd.to_datetime(f["Date"])
p = pd.read_csv("../price10y_1028.csv", usecols=["Date", "Ticker", "Open"])
p["Date"] = pd.to_datetime(p["Date"])
p["Ticker"] = p["Ticker"].astype(str).str.upper()
p = p.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")
price_map = {t: g["Date"].to_numpy() for t, g in p.groupby("Ticker")}
counts = {h: {"MATURED": 0, "NOT_MATURED": 0, "MISSING_PRICE": 0} for h in (1, 5, 10, 20, 60)}
for t, g in f.groupby("Ticker"):
    dates = g["Date"].to_numpy()
    pv = price_map.get(t)
    if pv is None:
        for h in counts:
            counts[h]["MISSING_PRICE"] += len(g)
        continue
    for h in counts:
        # first price strictly after signal
        pos = np.searchsorted(pv, dates, side="right")
        valid = pos < len(pv)
        counts[h]["MISSING_PRICE"] += int((~valid).sum())
        counts[h]["NOT_MATURED"] += int((valid & (pos + h >= len(pv))).sum())
        counts[h]["MATURED"] += int((valid & (pos + h < len(pv))).sum())

# Validate the vectorized rule against the real forward_return module on a sample.
sample = f.sample(n=min(5000, len(f)), random_state=42).copy()
sample["Technical_Date"] = sample["Date"].dt.strftime("%Y-%m-%d")
out = {"snapshot_rows": len(f), "method": "trading-session index; same rule as forward_return",
       "horizons": {str(h): counts[h] for h in counts}, "sample_validation": {}}
for h in (1, 5, 10, 20, 60):
    r = build_forward_returns(sample[["Ticker", "Technical_Date"]], p, horizons=(h,))
    out["sample_validation"][str(h)] = {str(k): int(v) for k, v in r["Sample_Status"].value_counts().items()}
Path("docs/research/factor_forward_label_maturity_2026-10-30.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
