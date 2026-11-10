#!/usr/bin/env python3
"""NON_OVERLAPPING_20D long-only portfolio experiment.

Signal at close, enter next open, hold exactly 20 sessions, exit at open, then
cash until the next signal (the prior exit close). 100% capital per period,
equal weight. Label: EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.research.portfolio_accounting import cagr, max_drawdown, sharpe

HOLD = 20
TOP = 0.20
MIN_PRICE = 5.0
MIN_DV = 5_000_000.0
MIN_NAMES = 80
COSTS = (10, 25, 50)
LABEL = "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED"
SIGNALS = {"Momentum20": "Mom20", "Momentum60": "Mom60", "Trend": "Trend100",
           "RSI": "-RSI14", "MeanReversion": "Rev5", "LowVol": "LowVol20", "ATR": "ATR14"}


def load_panel(path):
    d = pd.read_csv(path, low_memory=False)
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d["Ticker"] = d["Ticker"].astype(str).str.upper().str.strip()
    for c in ("Open", "High", "Low", "Close", "Volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["Date", "Ticker", "Open", "Close"]).sort_values(["Ticker", "Date"])
    g = d.groupby("Ticker", sort=False)
    d["Mom20"] = g["Close"].transform(lambda s: s / s.shift(20) - 1)
    d["Mom60"] = g["Close"].transform(lambda s: s / s.shift(60) - 1)
    d["Trend100"] = g["Close"].transform(lambda s: s / s.rolling(100, min_periods=100).mean() - 1)
    d["Rev5"] = -g["Close"].transform(lambda s: s / s.shift(5) - 1)
    r = g["Close"].pct_change()
    d["LowVol20"] = -r.groupby(d["Ticker"]).transform(lambda s: s.rolling(20, min_periods=20).std() * np.sqrt(252))
    up = r.clip(lower=0).groupby(d["Ticker"]).transform(lambda s: s.rolling(14, min_periods=14).mean())
    dn = (-r.clip(upper=0)).groupby(d["Ticker"]).transform(lambda s: s.rolling(14, min_periods=14).mean())
    d["RSI14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    prev = g["Close"].shift(1)
    tr = pd.concat([(d.High - d.Low).abs(), (d.High - prev).abs(), (d.Low - prev).abs()], axis=1).max(axis=1)
    d["ATR14"] = -tr.groupby(d["Ticker"]).transform(lambda s: s.rolling(14, min_periods=14).mean()) / d.Close
    dv = d.Close * d.Volume
    d["DV20"] = dv.groupby(d["Ticker"]).transform(lambda s: s.rolling(20, min_periods=20).mean())
    return d


def schedule(calendar, start="2018-01-01"):
    cal = [pd.Timestamp(x) for x in calendar]
    i = next((j for j, x in enumerate(cal) if x >= pd.Timestamp(start)), None)
    out = []
    if i is None:
        return out
    while i + HOLD + 1 < len(cal):
        out.append({"signal": cal[i], "entry": cal[i + 1], "exit": cal[i + 1 + HOLD]})
        i = i + 1 + HOLD
    return out


def daily_equity(start_equity, entry, exit_, weights, open_px, close_px, calendar, cost_bps):
    # weights sum to 1; full buy at entry open, full sell at exit open.
    c = cost_bps / 10000
    invest = start_equity * (1 - c)
    shares = {t: invest * w / open_px[entry][t] for t, w in weights.items()}
    eq = []
    for dt in calendar:
        if dt < entry or dt > exit_:
            continue
        if dt == exit_:
            proceeds = sum(sh * open_px[exit_][t] for t, sh in shares.items()) * (1 - c)
            eq.append((dt, proceeds))
        else:
            eq.append((dt, sum(sh * close_px[dt][t] for t, sh in shares.items())))
    return eq


def metrics_from_daily(dates, equity):
    s = pd.Series(equity, index=pd.to_datetime(dates), dtype=float)
    r = s.pct_change().dropna()
    years = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
    return {"days": len(s), "cagr": float(cagr(r, years)), "sharpe": sharpe(r, 252),
            "max_drawdown": max_drawdown(r), "annualized_volatility": float(np.std(r, ddof=1) * np.sqrt(252)),
            "total_return": float(s.iloc[-1] / s.iloc[0] - 1)}


def run(price_path, spy_path, output):
    d = load_panel(price_path)
    calendar = sorted(pd.to_datetime(d.Date.unique()))
    opens = d.pivot_table(index="Date", columns="Ticker", values="Open", aggfunc="last")
    closes = d.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last")
    periods = schedule(calendar)
    out = {"label": LABEL, "hold_sessions": HOLD, "cost_bps_per_side": list(COSTS),
           "periods": {}, "invalid": [], "window": {"start": str(periods[0]["entry"].date()) if periods else None,
                                                     "end": str(periods[-1]["exit"].date()) if periods else None}}
    for name, col in SIGNALS.items():
        out["periods"][name] = {}
        for cost in COSTS:
            eq_dates, eq = [periods[0]["entry"] - pd.Timedelta(days=1)], [1.0]
            rows = []
            for p in periods:
                day = d[d.Date.eq(p["signal"])]
                factor_col = "RSI14" if col == "-RSI14" else col
                elig = day[(day.Close >= MIN_PRICE) & (day.DV20 >= MIN_DV)].dropna(subset=[factor_col])
                score = -elig["RSI14"] if col == "-RSI14" else elig[col]
                frame = elig.assign(Score=score).dropna(subset=["Score"]).sort_values(["Score", "Ticker"], ascending=[False, True])
                if len(frame) < MIN_NAMES:
                    out["invalid"].append({"strategy": name, "signal": str(p["signal"].date()), "reason": "insufficient_names"})
                    continue
                names = list(frame.head(max(1, int(len(frame) * TOP))).Ticker)
                if any(t not in opens.loc[p["entry"]] or t not in closes.loc[p["exit"]] for t in names):
                    out["invalid"].append({"strategy": name, "signal": str(p["signal"].date()), "reason": "selected_missing_price"})
                    continue
                if any(pd.isna(opens.loc[p["entry"], t]) or pd.isna(closes.loc[p["exit"], t]) for t in names):
                    out["invalid"].append({"strategy": name, "signal": str(p["signal"].date()), "reason": "selected_nan_price"})
                    continue
                w = {t: 1 / len(names) for t in names}
                # mark-to-market daily
                c = cost / 10000
                invest = eq[-1] * (1 - c)
                shares = {t: invest * w[t] / opens.loc[p["entry"], t] for t in names}
                for dt in calendar:
                    if dt < p["entry"] or dt > p["exit"]:
                        continue
                    if dt == p["exit"]:
                        val = sum(sh * opens.loc[p["exit"], t] for t, sh in shares.items()) * (1 - c)
                    else:
                        val = sum(sh * closes.loc[dt, t] for t, sh in shares.items())
                    eq_dates.append(dt); eq.append(float(val))
                gross = float(np.mean([opens.loc[p["exit"], t] / opens.loc[p["entry"], t] - 1 for t in names]))
                net = (1 - c) ** 2 * (1 + gross) - 1
                rows.append({"signal": str(p["signal"].date()), "entry": str(p["entry"].date()), "exit": str(p["exit"].date()),
                             "n": len(names), "gross": gross, "net": net, "names": names,
                             "weights": w, "cost": 2 * c})
            out["periods"][name][str(cost)] = {"periods": rows, "metrics": metrics_from_daily(eq_dates, eq),
                                               "equity": [[str(d.date()), float(v)] for d, v in zip(eq_dates, eq)]}
    # equal-weight benchmark same schedule/cost 10
    eq_dates, eq = [periods[0]["entry"] - pd.Timedelta(days=1)], [1.0]
    bench_rows = []
    for p in periods:
        day = d[d.Date.eq(p["signal"])]
        elig = day[(day.Close >= MIN_PRICE) & (day.DV20 >= MIN_DV)]
        names = list(elig.Ticker)
        if len(names) < MIN_NAMES or any(t not in opens.loc[p["entry"]] for t in names):
            continue
        c = 0.001
        invest = eq[-1] * (1 - c)
        shares = {t: invest / len(names) / opens.loc[p["entry"], t] for t in names}
        for dt in calendar:
            if dt < p["entry"] or dt > p["exit"]:
                continue
            if dt == p["exit"]:
                val = sum(sh * opens.loc[p["exit"], t] for t, sh in shares.items()) * (1 - c)
            else:
                val = sum(sh * closes.loc[dt, t] for t, sh in shares.items())
            eq_dates.append(dt); eq.append(float(val))
        bench_rows.append({"entry": str(p["entry"].date()), "exit": str(p["exit"].date()), "n": len(names)})
    out["equal_weight_10bps"] = {"metrics": metrics_from_daily(eq_dates, eq), "periods": bench_rows}
    # SPY buyhold from first entry to last exit
    spy = pd.read_csv(spy_path, usecols=["Date", "Close"])
    spy["Date"] = pd.to_datetime(spy["Date"])
    spy = spy[(spy.Date >= periods[0]["entry"]) & (spy.Date <= periods[-1]["exit"])].sort_values("Date")
    out["spy_buyhold"] = metrics_from_daily(spy.Date.tolist(), spy.Close.tolist())
    Path(output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"periods": len(periods), "invalid": len(out["invalid"])}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--spy", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(a.price_panel, a.spy, a.output)
