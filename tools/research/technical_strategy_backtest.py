#!/usr/bin/env python3
"""Exploratory 9-strategy technical backtest on the current 503-name panel.

Label: EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED.
Signal at month-end close, entry next open, exit 20 sessions later, top quintile.
Not PIT, not production, not a formal strategy ranking.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.research.portfolio_accounting import cagr, cost_units, max_drawdown, sharpe

HORIZON = 20
TOP = 0.20
MIN_PRICE = 5.0
MIN_DV = 5_000_000.0
MIN_NAMES = 80
LABEL = "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED"


def load_panel(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, low_memory=False)
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d["Ticker"] = d["Ticker"].astype(str).str.upper().str.strip()
    d = d.dropna(subset=["Date", "Ticker", "Open", "Close"]).copy()
    d = d[(d.Open > 0) & (d.Close > 0)]
    d = d.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")
    g = d.groupby("Ticker", sort=False)
    ret = g["Close"].pct_change()
    d["Ret1"] = ret
    d["Mom20"] = g["Close"].transform(lambda s: s / s.shift(20) - 1)
    d["Mom60"] = g["Close"].transform(lambda s: s / s.shift(60) - 1)
    d["Trend100"] = g["Close"].transform(lambda s: s / s.rolling(100, min_periods=100).mean() - 1)
    d["LowVol20"] = -ret.groupby(d["Ticker"]).transform(lambda s: s.rolling(20, min_periods=20).std() * np.sqrt(252))
    d["Rev5"] = -g["Close"].transform(lambda s: s / s.shift(5) - 1)
    up = ret.clip(lower=0).groupby(d["Ticker"]).transform(lambda s: s.rolling(14, min_periods=14).mean())
    dn = (-ret.clip(upper=0)).groupby(d["Ticker"]).transform(lambda s: s.rolling(14, min_periods=14).mean())
    d["RSI14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    # True range / close, lower is better; signal = -ATR.
    prev_close = g["Close"].shift(1)
    tr = pd.concat([(d.High - d.Low).abs(), (d.High - prev_close).abs(), (d.Low - prev_close).abs()], axis=1).max(axis=1)
    d["ATR14"] = -tr.groupby(d["Ticker"]).transform(lambda s: s.rolling(14, min_periods=14).mean()) / d["Close"]
    dv = d["Close"] * pd.to_numeric(d["Volume"], errors="coerce")
    d["DV20"] = dv.groupby(d["Ticker"]).transform(lambda s: s.rolling(20, min_periods=20).mean())
    d["EntryOpen"] = g["Open"].shift(-1)
    d["ExitOpen"] = g["Open"].shift(-(1 + HORIZON))
    d["Fwd20"] = d["ExitOpen"] / d["EntryOpen"] - 1
    return d


def month_ends(d):
    dates = pd.Series(pd.to_datetime(d.Date).unique())
    return sorted(dates.groupby(dates.dt.to_period("M")).max().tolist())


def stats(rows, column="gross"):
    r = np.asarray([x[column] for x in rows], dtype=float)
    n = len(r)
    if n < 3:
        return {"observations": n, "status": "INSUFFICIENT_DATA"}
    first = pd.Timestamp(rows[0]["entry_date"])
    last = pd.Timestamp(rows[-1]["exit_date"])
    years = max((last - first).days / 365.25, 1e-9)
    ppy = n / years
    vol = float(np.std(r, ddof=1) * np.sqrt(ppy))
    try:
        c = cagr(r, years)
    except ValueError:
        c = None
    return {"observations": n, "cagr": c, "annualized_volatility": vol,
            "sharpe": sharpe(r, ppy), "max_drawdown": max_drawdown(r),
            "mean_period": float(np.mean(r)), "periods_per_year": float(ppy)}


def spy_monthly(path, dates):
    d = pd.read_csv(path)
    d["Date"] = pd.to_datetime(d["Date"])
    d = d.sort_values("Date").reset_index(drop=True)
    out = []
    for dt in dates:
        pos = d.index[d.Date >= dt]
        if len(pos) == 0:
            continue
        i = int(pos[0]) + 1
        if i + HORIZON >= len(d):
            continue
        out.append(d.loc[i + HORIZON, "Open"] / d.loc[i, "Open"] - 1)
    return out


def run(panel_path, spy_path, output, start="2018-01-01", end=None):
    d = load_panel(panel_path)
    dates = [x for x in month_ends(d) if x >= pd.Timestamp(start) and (end is None or x <= pd.Timestamp(end))]
    calendar = sorted(pd.to_datetime(d.Date.unique()))
    calpos = {x: i for i, x in enumerate(calendar)}
    signals = {"Momentum20": "Mom20", "Momentum60": "Mom60", "Trend": "Trend100",
               "LowVol": "LowVol20", "MeanReversion": "Rev5", "RSI": "-RSI14", "ATR": "ATR14"}
    rows_by = {name: [] for name in signals}
    bench_rows = []
    prev = {name: set() for name in signals}
    prev_bench = set()
    for dt in dates:
        i = calpos[dt]
        if i + 1 + HORIZON >= len(calendar):
            continue
        entry_date, exit_date = calendar[i + 1], calendar[i + 1 + HORIZON]
        day = d[d.Date.eq(dt)].copy()
        elig = day[(day.Close >= MIN_PRICE) & (day.DV20 >= MIN_DV)]
        if len(elig) < MIN_NAMES or elig.Fwd20.isna().any():
            continue
        b = float(elig.Fwd20.mean())
        cu_b = cost_units(prev_bench, set(elig.Ticker), not prev_bench)
        bench_rows.append({"date": dt.date().isoformat(), "entry_date": str(entry_date.date()),
                           "exit_date": str(exit_date.date()), "gross": b,
                           "net_10": b - 0.001 * cu_b, "turnover": cu_b / 2})
        prev_bench = set(elig.Ticker)
        for name, col in signals.items():
            score = -elig.RSI14 if col == "-RSI14" else elig[col]
            frame = elig.assign(Score=score).dropna(subset=["Score"]).sort_values(["Score", "Ticker"], ascending=[False, True])
            if len(frame) < MIN_NAMES:
                continue
            selected = set(frame.head(max(1, int(len(frame) * TOP))).Ticker)
            picked = elig[elig.Ticker.isin(selected)]
            if len(picked) != len(selected) or picked.Fwd20.isna().any():
                continue
            cu = cost_units(prev[name], selected, not prev[name])
            gross = float(picked.Fwd20.mean())
            rows_by[name].append({"date": dt.date().isoformat(), "entry_date": str(entry_date.date()),
                                  "exit_date": str(exit_date.date()), "gross": gross,
                                  "turnover": cu / 2, "cost_units": cu, "benchmark": b})
            prev[name] = selected
    out = {"label": LABEL, "window": {"start": str(dates[0].date()), "end": str(dates[-1].date())},
           "cost_bps": [5, 10, 20], "strategies": {}}
    for name, rows in rows_by.items():
        out["strategies"][name] = {"gross": stats(rows), "mean_turnover": float(np.mean([x["turnover"] for x in rows])) if rows else None}
        for c in (5, 10, 20):
            for x in rows:
                x[f"net_{c}"] = x["gross"] - c / 10000 * x["cost_units"]
            out["strategies"][name][f"net_{c}bps"] = stats(rows, f"net_{c}")
        ex = [x["gross"] - x["benchmark"] for x in rows]
        out["strategies"][name]["excess_vs_ew_gross"] = {
            "mean_period": float(np.mean(ex)), "sharpe": sharpe(ex, len(ex) / max((pd.Timestamp(rows[-1]["exit_date"]) - pd.Timestamp(rows[0]["entry_date"])).days / 365.25, 1e-9)),
            "positive_fraction": float((np.asarray(ex) > 0).mean())}
    out["equal_weight"] = {"gross": stats(bench_rows, "gross"), "net_10bps": stats(bench_rows, "net_10")}
    spy_rows = []
    spy = pd.read_csv(spy_path, usecols=["Date", "Open"])
    spy["Date"] = pd.to_datetime(spy["Date"])
    smap = spy.set_index("Date")["Open"]
    for r in bench_rows:
        e, x = pd.Timestamp(r["entry_date"]), pd.Timestamp(r["exit_date"])
        if e in smap.index and x in smap.index:
            spy_rows.append({"entry_date": r["entry_date"], "exit_date": r["exit_date"],
                             "gross": float(smap[x] / smap[e] - 1)})
    out["spy_buyhold"] = {"gross": stats(spy_rows, "gross")}
    Path(output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--spy", required=True)
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(a.price_panel, a.spy, a.output, a.start, a.end)
