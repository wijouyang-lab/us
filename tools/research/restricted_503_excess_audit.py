#!/usr/bin/env python3
"""Paired excess-return audit for the fixed five factors.

Compares factor portfolios with the equal-weight benchmark on exactly the same
test dates, under both raw and same-date winsorized return processing.
No factor or parameter changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import tools.research.restricted_503_factor_expanded as bt


def _net_series(df, name, direction, dates, winsorize, common):
    prev_long, prev_short = set(), set()
    out = []
    for d in dates:
        base = common.get(d)
        if base is None:
            continue
        x = base[["Ticker", name, "Fwd20"]].dropna().copy()
        if len(x) < 80:
            continue
        lo, hi = x["Fwd20"].quantile(list(bt.WINSOR))
        x["r"] = x["Fwd20"].clip(lo, hi) if winsorize else x["Fwd20"]
        bench = float(x["r"].mean())
        rank = x[name].rank(pct=True)
        long, short = set(x[rank >= .8]["Ticker"]), set(x[rank <= .2]["Ticker"])
        q5 = x[x["Ticker"].isin(long)]["r"].mean()
        q1 = x[x["Ticker"].isin(short)]["r"].mean()
        turnover = 1.0 if not (prev_long or prev_short) else (
            len(long - prev_long) + len(short - prev_short)
        ) / max(len(long) + len(short), 1)
        cost = bt.COST_BPS / 10000.0 * turnover
        gross = direction * (q5 - q1)
        out.append({"date": d.date().isoformat(), "n": len(x),
                    "n_long": len(long), "n_short": len(short),
                    "gross": gross, "net": gross - cost,
                    "benchmark": bench, "excess": gross - cost - bench,
                    "turnover": turnover, "cost": cost,
                    "n_missing_label": int(len(base) - len(x))})
        prev_long, prev_short = long, short
    return out


def _bh(p):
    p = np.asarray(p, float)
    order = np.argsort(p)
    raw = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(raw[::-1])[::-1]
    out = np.empty(len(p))
    out[order] = np.minimum(q, 1.0)
    return out


def _nw_t(x, lag=1):
    x = np.asarray(x, float)
    n = len(x)
    mu = x.mean()
    e = x - mu
    var = float(e @ e) / n
    for l in range(1, lag + 1):
        gamma = float(e[l:] @ e[:-l]) / n
        var += 2 * (1 - l / (lag + 1)) * gamma
    se = np.sqrt(var / n)
    return float(mu / se) if se > 0 else None


def _metrics(rows, label):
    if len(rows) < 3:
        return {"n": len(rows), "status": "INSUFFICIENT"}
    x = np.asarray([r["excess"] for r in rows], float)
    n = np.asarray([r["net"] for r in rows], float)
    eq = np.cumprod(1 + x)
    dd = eq / np.maximum.accumulate(eq) - 1 if len(eq) else np.array([0.0])
    t = float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if x.std(ddof=1) > 0 else None
    tz = float(n.mean() / (n.std(ddof=1) / np.sqrt(len(n)))) if n.std(ddof=1) > 0 else None
    return {
        "sample": label, "n": len(x),
        "mean_excess": float(x.mean()),
        "ann_excess": float((1 + x.mean()) ** 12 - 1),
        "excess_vol_ann": float(x.std(ddof=1) * np.sqrt(12)),
        "excess_max_drawdown": float(dd.min()),
        "positive_excess_pct": float((x > 0).mean()),
        "paired_t": t,
        "paired_p": float(2 * stats.t.sf(abs(t), len(x) - 1)) if t is not None else None,
        "nw_t_lag1": _nw_t(x, 1),
        "net_mean": float(n.mean()),
        "net_vs_zero_t": tz,
        "net_vs_zero_p": float(2 * stats.t.sf(abs(tz), len(n) - 1)) if tz is not None else None,
    }


def run(panel_path, output_prefix):
    df = bt.load_panel(panel_path)
    dates = [d for d in bt.month_ends(df) if d >= pd.Timestamp("2023-01-01")]
    common = {}
    for d in dates:
        base = df[(df["Date"] == d) & (df["Close"] >= bt.MIN_PRICE) & (df["DV20"] >= bt.MIN_DOLLAR_VOLUME)]
        base = base[["Ticker", "Fwd20", *bt.FACTORS]].dropna()
        if len(base) >= 80:
            common[d] = base
    results = {}
    monthly = []
    for mode, winsorize in (("raw", False), ("winsorized", True)):
        factor_rows = {}
        for name, (direction, rationale) in bt.FACTORS.items():
            factor_rows[name] = _net_series(df, name, direction, dates, winsorize, common)
            for r in factor_rows[name]:
                monthly.append({"factor": name, "processing": mode, **r})
        for name, rows in factor_rows.items():
            m = _metrics(rows, f"test_2023_2026_{mode}")
            m.update({"factor": name, "processing": mode,
                      "rationale": bt.FACTORS[name][1]})
            results[f"{mode}:{name}"] = m
        # paired BH is applied within each processing mode across five factors
        ps = [results[f"{mode}:{n}"]["paired_p"] for n in bt.FACTORS]
        for name, q in zip(bt.FACTORS, _bh(ps)):
            results[f"{mode}:{name}"]["paired_bh_q"] = float(q)
        # auxiliary net-vs-zero BH, explicitly separate
        ps0 = [results[f"{mode}:{n}"]["net_vs_zero_p"] for n in bt.FACTORS]
        for name, q in zip(bt.FACTORS, _bh(ps0)):
            results[f"{mode}:{name}"]["net_vs_zero_bh_q"] = float(q)

    frame = pd.DataFrame(monthly).sort_values(["processing", "factor", "date"])
    Path(output_prefix).parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_prefix + "_monthly.csv", index=False)
    payload = {
        "panel": panel_path,
        "rows": int(len(df)),
        "tickers": int(df["Ticker"].nunique()),
        "sessions": int(df["Date"].nunique()),
        "date_min": str(df["Date"].min().date()),
        "date_max": str(df["Date"].max().date()),
        "test_month_ends": len(dates),
        "test_rows": int(frame["date"].nunique()),
        "processing_modes": ["raw", "winsorized"],
        "entry_assumption": "month-end close signal; zero execution lag; exploratory",
        "winsorization": "per rebalance date, same eligible universe, 1%/99%",
        "cost_bps": bt.COST_BPS,
        "horizon": bt.HORIZON,
        "results": list(results.values()),
    }
    Path(output_prefix + ".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--output-prefix", required=True)
    args = p.parse_args(argv)
    result = run(args.price_panel, args.output_prefix)
    print(json.dumps({k: result[k] for k in ("rows", "tickers", "sessions", "test_month_ends", "test_rows")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
