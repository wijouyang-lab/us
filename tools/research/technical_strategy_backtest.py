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


def stats(returns):
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n < 3:
        return {"observations": n, "status": "INSUFFICIENT_DATA"}
    eq = np.cumprod(1 + r)
    vol = np.std(r, ddof=1) * np.sqrt(12)
    ann = np.prod(1 + r) ** (12 / n) - 1
    return {"observations": n, "annualized_return": float(ann), "annualized_volatility": float(vol),
            "sharpe": float(ann / vol) if vol > 0 else None,
            "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min())}


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
    signals = {"Momentum20": "Mom20", "Momentum60": "Mom60", "Trend": "Trend100",
               "LowVol": "LowVol20", "MeanReversion": "Rev5", "RSI": "-RSI14", "ATR": "ATR14"}
    rows_by = {name: [] for name in signals}
    bench, spy = [], []
    prev = {name: set() for name in signals}
    prev_bench = set()
    for dt in dates:
        day = d[d.Date.eq(dt)].copy()
        elig = day[(day.Close >= MIN_PRICE) & (day.DV20 >= MIN_DV)]
        if len(elig) < MIN_NAMES or elig.Fwd20.isna().any():
            continue
        b = elig.Fwd20.mean()
        bench.append(b)
        # equal-weight benchmark turnover cost is captured by benchmark net later.
        for name, col in signals.items():
            if col == "-RSI14":
                score = -elig.RSI14
            else:
                score = elig[col]
            frame = elig.assign(Score=score).dropna(subset=["Score"]).sort_values(["Score", "Ticker"], ascending=[False, True])
            if len(frame) < MIN_NAMES:
                continue
            selected = set(frame.head(max(1, int(len(frame) * TOP))).Ticker)
            picked = elig[elig.Ticker.isin(selected)]
            if len(picked) != len(selected) or picked.Fwd20.isna().any():
                continue
            turnover = 1.0 if not prev[name] else len(selected - prev[name]) / max(len(selected), 1)
            # Cost is per side: first buy = 1x; replacement = buy + sell = 2x.
            cost_units = 1.0 if not prev[name] else 2.0 * turnover
            gross = float(picked.Fwd20.mean())
            rows_by[name].append({"date": dt.date().isoformat(), "gross": gross,
                                  "turnover": turnover, "cost_units": cost_units,
                                  "excess_vs_ew": gross - b})
            prev[name] = selected
    spy_returns = spy_monthly(spy_path, dates)
    n = min([len(v) for v in rows_by.values()] + [len(bench), len(spy_returns)])
    out = {"label": LABEL, "window": {"start": str(dates[0].date()), "end": str(dates[-1].date())},
           "n_months": n, "cost_bps": [5, 10, 20], "strategies": {}}
    for name, rows in rows_by.items():
        rows = rows[:n]
        out["strategies"][name] = {"gross": stats([x["gross"] for x in rows]),
                                  "mean_turnover": float(np.mean([x["turnover"] for x in rows])) if rows else None,
                                  "excess_vs_ew_gross": stats([x["excess_vs_ew"] for x in rows])}
        for c in (5, 10, 20):
            net = [x["gross"] - c / 10000 * x["cost_units"] for x in rows]
            out["strategies"][name][f"net_{c}bps"] = stats(net)
    out["equal_weight"] = {"gross": stats(bench[:n])}
    out["spy_buyhold"] = {"gross": stats(spy_returns[:n])}
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
