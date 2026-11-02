#!/usr/bin/env python3
"""Pre-registered single-factor ablations on the same panel/evaluate engine."""
from __future__ import annotations

import json
from pathlib import Path

from tools.research.qlib_inspired_low_frequency_strategy import evaluate, load_panel, month_ends

VARIANTS = {
    "momentum_12_1": {"Mom12_1": 1.0},
    "trend_100": {"Trend100": 1.0},
    "low_vol_60": {"LowVol60": 1.0},
    "reversal_5": {"Reversal5": 1.0},
    "composite": {"Mom12_1": 0.35, "Trend100": 0.25, "LowVol60": 0.20,
                   "Reversal5": 0.10, "DollarVolumeTrend": 0.10},
}


def main():
    panel = load_panel("../price10y_1028.csv")
    dates = month_ends(panel)
    out = {"research_only": True, "test_start": "2023-01-01", "cost_bps": 5.0,
           "variants": {}}
    for name, weights in VARIANTS.items():
        r = evaluate(panel, dates, cost_bps=5.0, weights=weights)
        out["variants"][name] = {"weights": weights, "metrics": r["metrics"], "rows": r["rows"]}
        m = r["metrics"]
        print(name, m["status"], m.get("strategy", {}).get("annualized_return"),
              m.get("excess_net", {}).get("annualized_return"))
    Path("docs/research/qlib_factor_ablations_2026-10-30.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
