#!/usr/bin/env python3
"""Fixed-five-factor chronological annual out-of-sample audit.

No factor selection, no parameter search, no random split. Signals are formed
at month-end close with the previously documented zero-lag exploratory
assumption; the test reports annual buckets so stability is visible.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import tools.research.restricted_503_factor_expanded as bt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--cost-bps", type=float, default=bt.COST_BPS)
    args = p.parse_args(argv)
    df = bt.load_panel(args.price_panel)
    dates = bt.month_ends(df)
    test_dates = [d for d in dates if d >= pd.Timestamp("2023-01-01")]
    sessions = list(pd.Series(df["Date"].unique()).sort_values())
    gaps = []
    for a, b in zip(test_dates, test_dates[1:]):
        ia, ib = sessions.index(a), sessions.index(b)
        gaps.append(ib - ia)
    overlapping = sum(g < bt.HORIZON for g in gaps)
    bench_rows = []
    for d in test_dates:
        x = df[(df["Date"] == d) & (df["Close"] >= bt.MIN_PRICE) & (df["DV20"] >= bt.MIN_DOLLAR_VOLUME)]
        x = x[["Fwd20"]].dropna()
        if len(x) >= 80:
            r = float(x["Fwd20"].mean())
            bench_rows.append({"date": d.date().isoformat(), "year": d.year,
                               "gross": r, "net": r, "turnover": 0.0,
                               "n": len(x), "n_long": 0, "n_short": 0})
    bench_by_year = {y: bt.metrics([r for r in bench_rows if r["year"] == y], str(y))
                     for y in sorted({r["year"] for r in bench_rows})}
    common_rows = []
    for d in test_dates:
        x = df[(df["Date"] == d) & (df["Close"] >= bt.MIN_PRICE) & (df["DV20"] >= bt.MIN_DOLLAR_VOLUME)]
        x = x[["Fwd20", *bt.FACTORS]].dropna()
        if len(x) >= 80:
            r = float(x["Fwd20"].mean())
            common_rows.append({"date": d.date().isoformat(), "year": d.year,
                                "gross": r, "net": r, "turnover": 0.0,
                                "n": len(x), "n_long": 0, "n_short": 0})
    common_by_year = {y: bt.metrics([r for r in common_rows if r["year"] == y], str(y))
                      for y in sorted({r["year"] for r in common_rows})}
    net_bench_rows = []
    for r in bench_rows:
        rr = dict(r)
        rr["turnover"] = 1.0
        rr["net"] = rr["gross"] - args.cost_bps / 10000.0
        rr["cost"] = args.cost_bps / 10000.0
        net_bench_rows.append(rr)
    net_bench_by_year = {y: bt.metrics([r for r in net_bench_rows if r["year"] == y], str(y))
                         for y in sorted({r["year"] for r in net_bench_rows})}
    records = []
    for name, (direction, _) in bt.FACTORS.items():
        rows = bt.evaluate(df, name, direction, test_dates, cost_bps=args.cost_bps)["rows"]
        for y in sorted({r["date"][:4] for r in rows}):
            m = bt.metrics([r for r in rows if r["date"].startswith(y)], y)
            b_common = common_by_year.get(int(y), {})
            b_net = net_bench_by_year.get(int(y), {})
            m.update({"factor": name, "year": int(y),
                      "benchmark_ann": bench_by_year.get(int(y), {}).get("ann_return"),
                      "benchmark_common_ann": b_common.get("ann_return"),
                      "benchmark_net_ann": b_net.get("ann_return"),
                      "excess_vs_common_ann": m["ann_return"] - b_common["ann_return"] if b_common.get("ann_return") is not None else None,
                      "excess_vs_net_ann": m["ann_return"] - b_net["ann_return"] if b_net.get("ann_return") is not None else None})
            records.append(m)
    out = pd.DataFrame(records).sort_values(["year", "factor"])
    out.to_csv(args.output_prefix + "_annual.csv", index=False)
    payload = {
        "rows": int(len(df)), "tickers": int(df["Ticker"].nunique()),
        "date_min": str(df["Date"].min().date()), "date_max": str(df["Date"].max().date()),
        "test_years": sorted({int(r["year"]) for r in records}),
        "benchmark_by_year": bench_by_year,
        "benchmark_common_by_year": common_by_year,
        "benchmark_net_by_year": net_bench_by_year,
        "annual": out.to_dict(orient="records"),
        "cost_bps": args.cost_bps,
        "cost_convention": "bps per unit one-way book turnover; initial book = 1.0; benchmark has zero turnover and zero cost in benchmark_by_year",
        "benchmark_cost": "original benchmark: zero turnover/cost; benchmark_net_by_year applies a full 1.0 monthly rebalance turnover at cost_bps",
        "benchmark_common": "same eligible universe, requiring all five factor values plus Fwd20",
        "test_date_count": len(test_dates),
        "overlapping_windows": overlapping,
        "horizon_sessions": bt.HORIZON,
        "factor_directions": {k: v[0] for k, v in bt.FACTORS.items()},
        "universe": "current 503-name panel, complete history not guaranteed; survivorship-biased",
        "entry_assumption": "month-end close signal, zero execution lag, exploratory",
        "multiple_testing": "annual metrics descriptive; no q-value claim across years",
        "note": "fixed factors; no selection or parameter search",
    }
    Path(args.output_prefix + ".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out[["year", "factor", "n", "net_mean", "ann_return", "sharpe", "benchmark_ann"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
