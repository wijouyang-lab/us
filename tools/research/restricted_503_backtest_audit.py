#!/usr/bin/env python3
"""Audit fixed-factor backtest alignment and test-scope benchmark.

Does not change factors, parameters, or the original result files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import tools.research.restricted_503_factor_validation as bt


def run(panel_path: str, output_prefix: str) -> dict:
    df = bt.load_panel(panel_path)
    all_dates = bt.month_ends(df)
    test_dates = [d for d in all_dates if d >= pd.Timestamp("2023-01-01")]
    sessions = sorted(df["Date"].unique())
    rows = []
    factor_rows = {}
    for name in bt.FACTORS:
        factor_rows[name] = {r["date"]: r for r in bt.evaluate(df, name, bt.FACTORS[name][0], test_dates)["rows"]}
    for d in test_dates:
        x_all = df[(df["Date"] == d) & (df["Close"] >= bt.MIN_PRICE) & (df["DV20"] >= bt.MIN_DOLLAR_VOLUME)]
        x_lab = x_all[["Ticker", "Fwd20"]].dropna()
        if len(x_lab) < 80:
            continue
        idx = sessions.index(d)
        exit_date = sessions[idx + bt.HORIZON].date().isoformat() if idx + bt.HORIZON < len(sessions) else None
        row = {
            "signal_date": d.date().isoformat(),
            "entry_date_assumption": d.date().isoformat(),
            "exit_date_20_sessions": exit_date,
            "n_eligible": len(x_all),
            "n_labeled": len(x_lab),
            "n_missing_label": len(x_all) - len(x_lab),
            "benchmark_net": float(x_lab["Fwd20"].mean()),
        }
        for name, by_date in factor_rows.items():
            f = by_date.get(d.date().isoformat())
            if f:
                row[f"{name}_gross"] = f["gross"]
                row[f"{name}_net"] = f["net"]
                row[f"{name}_turnover"] = f["turnover"]
                row[f"{name}_cost"] = f["cost"]
        rows.append(row)
    audit = pd.DataFrame(rows)
    Path(output_prefix).parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_prefix + ".csv", index=False)
    bench_test = bt.benchmark(df, test_dates)
    bench_full = bt.benchmark(df, all_dates)
    factor_metrics = {}
    for name in bt.FACTORS:
        subset = [r for r in factor_rows[name].values()]
        factor_metrics[name] = bt.metrics(subset, "test_2023_2026")
    result = {
        "panel": panel_path,
        "rows": int(len(df)),
        "tickers": int(df["Ticker"].nunique()),
        "sessions": int(df["Date"].nunique()),
        "date_min": str(df["Date"].min().date()),
        "date_max": str(df["Date"].max().date()),
        "all_month_ends": len(all_dates),
        "test_month_ends": len(test_dates),
        "audit_rows": int(len(audit)),
        "benchmark_test": bench_test,
        "benchmark_full": bench_full,
        "factor_metrics_test": factor_metrics,
        "monthly_audit": audit.to_dict(orient="records"),
    }
    Path(output_prefix + ".json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--output-prefix", required=True)
    args = p.parse_args(argv)
    result = run(args.price_panel, args.output_prefix)
    print(json.dumps({
        "rows": result["rows"], "tickers": result["tickers"],
        "sessions": result["sessions"], "all_month_ends": result["all_month_ends"],
        "test_month_ends": result["test_month_ends"], "audit_rows": result["audit_rows"],
        "benchmark_test": result["benchmark_test"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
