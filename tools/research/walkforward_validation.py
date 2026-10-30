#!/usr/bin/env python3
"""Walk-forward validation for Momentum20, Momentum60 and Trend.

Fixed parameters only. Test years 2021-2026; 3-year pre-window context.
Selection uses signal-time data only; missing future prices skip the cohort.
Label: EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.research.technical_strategy_backtest import load_panel, month_ends

LABEL = "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED"
STRATEGIES = {"Momentum20": "Mom20", "Momentum60": "Mom60", "Trend": "Trend100"}
COSTS = (5, 10, 20, 50)


def metrics(returns):
    r = np.asarray(returns, float)
    if len(r) < 3:
        return {"observations": len(r), "status": "INSUFFICIENT_DATA"}
    eq = np.cumprod(1 + r)
    vol = float(np.std(r, ddof=1) * np.sqrt(12))
    ann = float(np.prod(1 + r) ** (12 / len(r)) - 1)
    return {"observations": len(r), "cagr": ann, "volatility": vol,
            "sharpe": ann / vol if vol else None,
            "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min())}


def spy_context(spy_path):
    d = pd.read_csv(spy_path)
    d["Date"] = pd.to_datetime(d["Date"])
    d = d.sort_values("Date").reset_index(drop=True)
    d["MA200"] = d.Close.rolling(200, min_periods=200).mean()
    d["Vol20"] = d.Close.pct_change().rolling(20, min_periods=20).std() * np.sqrt(252)
    d["Ret200"] = d.Close / d.Close.shift(200) - 1
    return d


def regime_at(spy, dt):
    s = spy[spy.Date <= dt].iloc[-1]
    trend = "bull" if s.Close >= s.MA200 else "bear"
    vol = "high_vol" if s.Vol20 >= 0.20 else "low_vol"
    regime = "trend" if abs(s.Ret200) >= 0.10 else "range"
    return {"trend": trend, "vol": vol, "regime": regime}


def run(panel_path, spy_path, output):
    d = load_panel(panel_path)
    spy = spy_context(spy_path)
    all_rows = []
    monthly = []
    ew_by_year = {}
    for year in range(2021, 2027):
        start = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(f"{year}-12-31")
        dates = [x for x in month_ends(d) if start <= x <= end]
        ew_by_year[year] = []
        for dt in dates:
            day = d[d.Date.eq(dt)].copy()
            elig = day[(day.Close >= 5.0) & (day.DV20 >= 5_000_000.0)]
            if len(elig) >= 80 and not elig.Fwd20.isna().any():
                ew_by_year[year].append(float(elig.Fwd20.mean()))
        for name, col in STRATEGIES.items():
            prev = set()
            rows = []
            for dt in dates:
                day = d[d.Date.eq(dt)].copy()
                elig = day[(day.Close >= 5.0) & (day.DV20 >= 5_000_000.0)]
                if len(elig) < 80:
                    continue
                score = elig[col].copy()
                frame = elig.assign(Score=score).dropna(subset=["Score"]).sort_values(["Score", "Ticker"], ascending=[False, True])
                selected = set(frame.head(max(1, int(len(frame) * 0.20))).Ticker)
                picked = elig[elig.Ticker.isin(selected)]
                if len(picked) != len(selected) or picked.Fwd20.isna().any():
                    continue
                turnover = 1.0 if not prev else len(selected - prev) / max(len(selected), 1)
                cost_units = 1.0 if not prev else 2.0 * turnover
                gross = float(picked.Fwd20.mean())
                reg = regime_at(spy, dt)
                rows.append({"date": dt.date().isoformat(), "gross": gross,
                             "turnover": turnover, "cost_units": cost_units,
                             "trades": len(selected - prev), **reg})
                monthly.append(dict(rows[-1], strategy=name, year=year))
                prev = selected
            if len(rows) < 3:
                continue
            base = {"year": year, "strategy": name, "months": len(rows),
                    "mean_turnover": float(np.mean([x["turnover"] for x in rows])),
                    "trades": int(sum(x["trades"] for x in rows))}
            for c in COSTS:
                net = [x["gross"] - c / 10000 * x["cost_units"] for x in rows]
                base[f"net_{c}bps"] = metrics(net)
            all_rows.append(base)
    # SPY buyhold per test year (close-to-close over the test window)
    spy_rows = []
    for year in range(2021, 2027):
        start = pd.Timestamp(f"{year}-01-01"); end = pd.Timestamp(f"{year}-12-31")
        s = spy[(spy.Date >= start) & (spy.Date <= end)]
        if len(s) >= 2:
            years = (s.Date.iloc[-1] - s.Date.iloc[0]).days / 365.25
            spy_rows.append({"year": year, "return": float((s.Close.iloc[-1] / s.Close.iloc[0]) ** (1 / years) - 1)})
    spy_by_year = {r["year"]: r["return"] for r in spy_rows}
    for r in all_rows:
        ew = metrics(ew_by_year.get(r["year"], []))
        r["ew_cagr"] = ew.get("cagr")
        r["excess_ew_10bps"] = (r["net_10bps"]["cagr"] - ew["cagr"]) if ew.get("cagr") is not None else None
        r["spy_cagr"] = spy_by_year.get(r["year"])
        r["excess_spy_10bps"] = (r["net_10bps"]["cagr"] - spy_by_year[r["year"]]) if r["year"] in spy_by_year else None
    # environment aggregation on 10 bps net
    regime = {}
    for name in STRATEGIES:
        subset = [r for r in monthly if r["strategy"] == name]
        if not subset:
            continue
        regime[name] = {}
        for key in ("trend", "vol", "regime"):
            groups = {}
            for value in sorted({r[key] for r in subset}):
                rows = [r for r in subset if r[key] == value]
                net = [r["gross"] - 10 / 10000 * r["cost_units"] for r in rows]
                groups[value] = {**metrics(net), "months": len(rows)}
            regime[name][key] = groups
    payload = {"label": LABEL, "test_years": "2021-2026", "train_context": "2018-2020",
               "cost_bps_per_side": list(COSTS), "windows": all_rows,
               "regime_10bps": regime,
               "spy_buyhold_cagr_by_year": spy_rows}
    Path(output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--spy", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(a.price_panel, a.spy, a.output)
