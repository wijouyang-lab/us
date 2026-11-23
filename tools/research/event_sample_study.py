import json
from pathlib import Path
import pandas as pd
from tools.research.forward_return import build_forward_returns

e = pd.read_csv("docs/research/sec_event_factors_2026-10-30.csv", dtype=str)
e["Technical_Date"] = e["trade_date"]
p = pd.read_csv("../price10y_1028.csv", usecols=["Date", "Ticker", "Open"])
out = {"label": "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED", "events": len(e), "horizons": {}}
for h in (1, 5, 10, 20, 60):
    r = build_forward_returns(e[["ticker", "Technical_Date"]].rename(columns={"ticker": "Ticker"}), p, horizons=(h,))
    m = e.reset_index(drop=True).join(r[["Forward_Return", "Sample_Status"]])
    m = m[m.Sample_Status == "MATURED"]
    out["horizons"][str(h)] = {"matured": len(m), "mean_return": float(m.Forward_Return.mean()) if len(m) else None,
                               "median_return": float(m.Forward_Return.median()) if len(m) else None,
                               "positive_fraction": float((m.Forward_Return > 0).mean()) if len(m) else None}
Path("docs/research/sec_event_study_sample_2026-10-30.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
