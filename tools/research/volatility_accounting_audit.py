#!/usr/bin/env python3
"""Independent accounting audit of Phase 2.7 long/short volatility portfolios.

Rebuilds costs from selected members and compares corrected short-leg accounting
against the original result. Does not modify Phase 2.7 files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

COSTS = (10, 25, 50)


def cost_units(prev, cur, initial):
    if initial or not prev:
        return 1.0
    return 2.0 * len(set(cur) - set(prev)) / max(len(cur), 1)


def stats(periods, first_entry, last_exit):
    r = np.asarray([p["net"] for p in periods], float)
    if len(r) < 3:
        return {"periods": len(r), "status": "INSUFFICIENT"}
    years = max((pd.Timestamp(last_exit) - pd.Timestamp(first_entry)).days / 365.25, 1e-9)
    eq = np.cumprod(1 + r)
    vol = np.std(r, ddof=1) * np.sqrt(252 / 60)
    mean = np.mean(r)
    return {"periods": len(r), "years": years,
            "cagr": float(np.prod(1 + r) ** (1 / years) - 1),
            "mean_period": float(mean), "volatility": float(vol),
            "sharpe": float(mean / vol * np.sqrt(252 / 60)) if vol > 0 else None,
            "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min())}


def run(input_path, output):
    d = json.loads(Path(input_path).read_text(encoding="utf-8"))
    out = {"label": "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED",
           "accounting": "long 1 unit + short 1 unit; gross exposure 2; capital denominator 2",
           "factors": {}, "violations": []}
    for factor, port in d["periods"].items():
        out["factors"][factor] = {}
        for wname, rows in port.items():
            prev1, prev5 = set(), set()
            rebuilt = []
            for i, r in enumerate(rows):
                q1, q5 = set(r["q1"]), set(r["q5"])
                cu1 = cost_units(prev1, q1, i == 0)
                cu5 = cost_units(prev5, q5, i == 0)
                rec = {"signal": r["signal"], "entry": r["entry"], "exit": r["exit"],
                       "gross_q1": r["gross_q1"], "gross_q5": r["gross_q5"],
                       "gross_spread": r["gross_q5"] - r["gross_q1"],
                       "cu_q1": cu1, "cu_q5": cu5}
                for c in COSTS:
                    c1 = c / 10000 * cu1
                    c5 = c / 10000 * cu5
                    rec[f"q5_net_{c}"] = r["gross_q5"] - c5
                    # short leg: -Q1 return minus its own cost
                    rec[f"q1_short_net_{c}"] = -r["gross_q1"] - c1
                    rec[f"spread_net_1x_{c}"] = rec[f"q5_net_{c}"] + rec[f"q1_short_net_{c}"]
                    rec[f"spread_net_2x_{c}"] = rec[f"spread_net_1x_{c}"] / 2
                rec["original_spread_10"] = r["net_10_q5_q1"]
                rec["original_spread_50"] = r["net_50_q5_q1"]
                rebuilt.append(rec)
                prev1, prev5 = q1, q5
            out["factors"][factor][wname] = {
                "periods": rebuilt,
                "metrics": {
                    str(c): {
                        "q5": stats([{"net": x[f"q5_net_{c}"]} for x in rebuilt], rebuilt[0]["entry"], rebuilt[-1]["exit"]),
                        "q1_short": stats([{"net": x[f"q1_short_net_{c}"]} for x in rebuilt], rebuilt[0]["entry"], rebuilt[-1]["exit"]),
                        "spread_1x": stats([{"net": x[f"spread_net_1x_{c}"]} for x in rebuilt], rebuilt[0]["entry"], rebuilt[-1]["exit"]),
                        "spread_2x": stats([{"net": x[f"spread_net_2x_{c}"]} for x in rebuilt], rebuilt[0]["entry"], rebuilt[-1]["exit"]),
                    } for c in COSTS
                }
            }
            for c in COSTS:
                q5 = [x[f"q5_net_{c}"] for x in rebuilt]
                q1 = [x[f"q1_short_net_{c}"] for x in rebuilt]
                if any(q5[i] > q5[i-1] + 1e-12 for i in range(1, len(q5))):
                    pass
                if any(q1[i] > q1[i-1] + 1e-12 for i in range(1, len(q1))):
                    pass
            out["factors"][factor][wname]["per_period"] = rebuilt
    Path(output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    rows = []
    for factor, ports in out["factors"].items():
        for w, p in ports.items():
            for c, m in p["metrics"].items():
                rows.append({"factor": factor, "weight": w, "cost_bps": c,
                             "q5_cagr": m["q5"]["cagr"], "q1_short_cagr": m["q1_short"]["cagr"],
                             "spread_1x_cagr": m["spread_1x"]["cagr"],
                             "spread_2x_cagr": m["spread_2x"]["cagr"],
                             "spread_2x_sharpe": m["spread_2x"]["sharpe"],
                             "spread_2x_dd": m["spread_2x"]["max_drawdown"]})
    pd.DataFrame(rows).to_csv(str(Path(output).with_suffix(".csv")), index=False)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(a.input, a.output)
