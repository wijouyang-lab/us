#!/usr/bin/env python3
"""Phase 2.7: non-overlapping 60D volatility portfolios with costs.

Label: EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED.
No PIT claim. No production changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

FACTORS = ("ATR_Percent", "Realized_Volatility_20D", "Beta_60D")
COSTS = (10, 25, 50)
HOLD = 60
MAX_WEIGHT = 0.05
LABEL = "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED"


def weights_equal(names):
    return {n: 1 / len(names) for n in names} if names else {}


def weights_inv_vol(names, vol):
    vals = {n: 1 / max(float(vol[n]), 1e-6) for n in names if pd.notna(vol.get(n)) and vol[n] > 0}
    if not vals:
        return weights_equal(names)
    total = sum(vals.values())
    w = {n: v / total for n, v in vals.items()}
    # cap and redistribute
    for _ in range(20):
        over = {n: x for n, x in w.items() if x > MAX_WEIGHT}
        if not over:
            break
        excess = sum(x - MAX_WEIGHT for x in over.values())
        for n in over:
            w[n] = MAX_WEIGHT
        rest = [n for n in w if n not in over]
        base = sum(w[n] for n in rest)
        if base <= 0:
            break
        for n in rest:
            w[n] += excess * w[n] / base
    s = sum(w.values())
    return {n: v / s for n, v in w.items()}


def period_return(weights, ret):
    return float(sum(w * float(ret[t]) for t, w in weights.items()))


def cost_units(previous, current, initial=True):
    if initial or not previous:
        return 1.0
    turnover = len(set(current) - set(previous)) / max(len(current), 1)
    return 2.0 * turnover


def build_schedule(dates, start="2018-01-01", hold=HOLD):
    dates = [pd.Timestamp(d) for d in dates]
    i = next((j for j, d in enumerate(dates) if d >= pd.Timestamp(start)), None)
    out = []
    if i is None:
        return out
    while i + hold + 1 < len(dates):
        entry_i, exit_i = i + 1, i + 1 + hold
        out.append((dates[i], dates[entry_i], dates[exit_i]))
        i = exit_i
    return out


def metrics(periods):
    r = np.asarray([p["net"] for p in periods], float)
    if len(r) < 3:
        return {"periods": len(r), "status": "INSUFFICIENT"}
    eq = np.cumprod(1 + r)
    days = sum(p["days"] for p in periods)
    years = days / 365.25
    cagr = np.prod(1 + r) ** (1 / years) - 1 if years > 0 else None
    vol = np.std(r, ddof=1) * np.sqrt(252 / HOLD)
    return {"periods": len(r), "cagr": float(cagr), "volatility": float(vol),
            "sharpe": float(cagr / vol) if vol > 0 else None,
            "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min()),
            "positive_period_fraction": float((r > 0).mean()),
            "mean_turnover": float(np.mean([p["turnover"] for p in periods])),
            "mean_cost": float(np.mean([p["cost"] for p in periods])),
            "trades": int(sum(p["trades"] for p in periods))}


def run(factor_path, spy_path, output):
    f = pd.read_parquet(factor_path)
    f["Date"] = pd.to_datetime(f["Date"])
    f["Ticker"] = f["Ticker"].astype(str).str.upper()
    f = f.sort_values(["Ticker", "Date"])
    dv = f["Close"] * f["Volume"]
    f["DV20"] = dv.groupby(f["Ticker"]).transform(lambda s: s.rolling(20, min_periods=20).mean())
    spy = pd.read_csv(spy_path, usecols=["Date", "Open", "Close"])
    spy["Date"] = pd.to_datetime(spy["Date"])
    dates = sorted(f.Date.unique())
    out = {"label": LABEL, "hold_sessions": HOLD, "cost_bps_per_side": list(COSTS),
           "test_start": "2018-01-01", "periods": {}, "benchmarks": {}, "invalid": []}
    # Build non-overlapping schedule: signal t close, entry t+1 open, exit t+61 open.
    schedule = build_schedule(dates)
    for factor in FACTORS:
        port = {}
        prev = {}
        for wname in ("equal", "inv_vol"):
            rows = []
            prev = {}
            for sig, entry, exit in schedule:
                day = f[f.Date.eq(sig)].copy()
                day = day[(day.Close >= 5) & (day.DV20 >= 5_000_000)].dropna(subset=[factor])
                if len(day) < 80:
                    out["invalid"].append({"factor": factor, "weight": wname, "signal": str(sig.date()), "reason": "insufficient_names"})
                    continue
                day["q"] = pd.qcut(day[factor].rank(method="first"), 5, labels=False)
                needed = set(day[day.q.isin([0, 4])].Ticker)
                # entry/exit prices from same factor panel
                ent = f[f.Date.eq(entry)][["Ticker", "Open"]].set_index("Ticker")["Open"]
                ext = f[f.Date.eq(exit)][["Ticker", "Open"]].set_index("Ticker")["Open"]
                rets = ext / ent - 1
                vol = day.set_index("Ticker")["Realized_Volatility_20D"] if "Realized_Volatility_20D" in day else pd.Series(dtype=float)
                q1 = set(day[day.q.eq(0)].Ticker); q5 = set(day[day.q.eq(4)].Ticker)
                if any(t not in rets.index or pd.isna(rets[t]) for t in q1 | q5):
                    out["invalid"].append({"factor": factor, "weight": wname, "signal": str(sig.date()), "reason": "selected_missing_price"})
                    continue
                rec = {"signal": str(sig.date()), "entry": str(entry.date()), "exit": str(exit.date()),
                       "n": len(day), "q1": sorted(q1), "q5": sorted(q5)}
                w1 = weights_equal(q1) if wname == "equal" else weights_inv_vol(q1, vol)
                w5 = weights_equal(q5) if wname == "equal" else weights_inv_vol(q5, vol)
                g1, g5 = period_return(w1, rets), period_return(w5, rets)
                rec["gross_q1"], rec["gross_q5"], rec["gross_q5_q1"] = g1, g5, g5 - g1
                rec["weights_q1"], rec["weights_q5"] = w1, w5
                for c in COSTS:
                    # long Q1 and Q5 costs separately; Q5-Q1 spread costs are sum of two legs.
                    cu1 = cost_units(prev.get("q1"), q1, not prev)
                    cu5 = cost_units(prev.get("q5"), q5, not prev)
                    cost1 = c / 10000 * cu1
                    cost5 = c / 10000 * cu5
                    rec[f"net_{c}_q1"] = g1 - cost1
                    rec[f"net_{c}_q5"] = g5 - cost5
                    rec[f"net_{c}_q5_q1"] = (g5 - cost5) - (g1 - cost1)
                rec["turnover"] = (cost_units(prev.get("q1"), q1, not prev) + cost_units(prev.get("q5"), q5, not prev)) / 2
                rec["cost"] = 10 / 10000 * cost_units(prev.get("q1"), q1, not prev)
                rec["trades"] = len(q1 ^ prev.get("q1", set())) + len(q5 ^ prev.get("q5", set()))
                rec["days"] = (exit - entry).days
                rows.append(rec)
                prev = {"q1": q1, "q5": q5}
            port[wname] = rows
        out["periods"][factor] = port
    # benchmarks using all factor dates and same schedule
    bench = []
    prev = set()
    for sig, entry, exit in schedule:
        day = f[f.Date.eq(sig)].copy()
        day = day[(day.Close >= 5) & (day.DV20 >= 5_000_000)]
        ent = f[f.Date.eq(entry)][["Ticker", "Open"]].set_index("Ticker")["Open"]
        ext = f[f.Date.eq(exit)][["Ticker", "Open"]].set_index("Ticker")["Open"]
        rets = (ext / ent - 1).dropna()
        names = set(day.Ticker) & set(rets.index)
        if len(names) < 80:
            continue
        w = weights_equal(names)
        g = period_return(w, rets)
        cu = 1.0 if not prev else 2.0 * len(names - prev) / max(len(names), 1)
        bench.append({"signal": str(sig.date()), "gross": g, "net_10": g - 0.001 * cu,
                      "turnover": cu / 2, "days": (exit - entry).days})
        prev = names
    out["benchmarks"]["equal_weight"] = {"gross": metrics([{"net": x["gross"], "days": x["days"], "turnover": x["turnover"], "cost": 0, "trades": 0} for x in bench]),
                                         "net_10": metrics([{"net": x["net_10"], "days": x["days"], "turnover": x["turnover"], "cost": 0, "trades": 0} for x in bench])}
    # SPY buyhold over each schedule period
    spy_rows = []
    smap = spy.set_index("Date")["Open"]
    for _, entry, exit in schedule:
        if entry in smap.index and exit in smap.index:
            spy_rows.append({"net": float(smap[exit] / smap[entry] - 1), "days": (exit - entry).days, "turnover": 0, "cost": 0, "trades": 0})
    out["benchmarks"]["spy_buyhold"] = metrics(spy_rows)
    # summarise
    summary = []
    for factor, port in out["periods"].items():
        for wname, rows in port.items():
            for c in COSTS:
                for leg in ("q1", "q5", "q5_q1"):
                    summary.append({"factor": factor, "weight": wname, "cost_bps": c, "leg": leg,
                                    **metrics([{"net": r[f"net_{c}_{leg}"], "days": r["days"], "turnover": r["turnover"], "cost": r["cost"], "trades": r["trades"]} for r in rows])})
    out["summary"] = summary
    Path(output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"schedule_periods": len(schedule), "summary_rows": len(summary),
                      "invalid": len(out["invalid"])}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--factors", required=True)
    p.add_argument("--spy", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(a.factors, a.spy, a.output)
