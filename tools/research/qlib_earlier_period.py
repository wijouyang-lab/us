import json
from pathlib import Path
import pandas as pd
from tools.research.qlib_inspired_low_frequency_strategy import load_panel, month_ends, evaluate

panel = load_panel("../price10y_1028.csv")
dates = month_ends(panel)
early = [d for d in dates if pd.Timestamp(d) < pd.Timestamp("2023-01-01")]
w = {"Mom12_1": 0.35, "Trend100": 0.25, "LowVol60": 0.20, "Reversal5": 0.10, "DollarVolumeTrend": 0.10}
out = {}
for name, weights in {"composite": w, "momentum_12_1": {"Mom12_1": 1.0}}.items():
    r = evaluate(panel, early, cost_bps=10.0, test_start="2018-01-01", weights=weights)
    out[name] = r["metrics"]
Path("docs/research/qlib_earlier_period_2018_2022_2026-10-30.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
