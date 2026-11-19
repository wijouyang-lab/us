#!/usr/bin/env python3
"""P13 ATR_Pct 3Y/5Y validation. Local data only; no network, no orders."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def wilder(s, n=14):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def atr_frame(g):
    prev = g["close"].shift(1)
    tr = pd.concat([(g["high"] - g["low"]).abs(), (g["high"] - prev).abs(), (g["low"] - prev).abs()], axis=1).max(axis=1)
    return wilder(tr, 14) / g["close"]


def hac_t(x, lag=4):
    x = np.asarray(x, float); n = len(x); e = x - x.mean(); v = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(v / n) if v > 0 else np.nan


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); q = np.empty(n); prev = 1.0
    for rank in range(n - 1, -1, -1):
        i = o[rank]; prev = min(prev, p[i] * n / (rank + 1)); q[i] = prev
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", type=Path, required=True)
    ap.add_argument("--members", type=Path, required=True)
    ap.add_argument("--spy", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(a.prices, usecols=["date", "symbol", "open", "high", "low", "close", "adjusted_close"])
    raw["date"] = pd.to_datetime(raw.date)
    raw = raw.dropna().sort_values(["symbol", "date"])
    raw["atr_pct"] = raw.groupby("symbol", group_keys=False).apply(atr_frame)
    raw["fwd20"] = raw.groupby("symbol").adjusted_close.shift(-20) / raw.adjusted_close - 1
    raw["fwd5"] = raw.groupby("symbol").adjusted_close.shift(-5) / raw.adjusted_close - 1
    raw["fwd10"] = raw.groupby("symbol").adjusted_close.shift(-10) / raw.adjusted_close - 1
    spy = pd.read_csv(a.spy, usecols=["Date", "close"]); spy["date"] = pd.to_datetime(spy.Date, utc=True).dt.tz_convert(None).dt.normalize()
    spy = spy.set_index("date")["close"].sort_index()
    for h in (5, 10, 20):
        raw[f"spy{h}"] = raw.date.map(spy.shift(-h) / spy - 1)
        raw[f"ex{h}"] = raw[f"fwd{h}"] - raw[f"spy{h}"]
    mem = pd.read_csv(a.members)
    mem["date"] = pd.to_datetime(mem.date)
    import bisect
    snap_dates = sorted(set(mem.date))
    members = {d: set(str(t).split(",")) for d, t in zip(mem.date, mem.tickers)}
    start, end = pd.Timestamp("2020-01-01"), raw.date.max()
    p = raw[(raw.date >= start) & (raw.date <= end)].copy()

    def members_at(d):
        i = bisect.bisect_right(snap_dates, d) - 1
        return members.get(snap_dates[i], set()) if i >= 0 else set()
    p["member"] = [sym in members_at(d) for d, sym in zip(p.date, p.symbol)]
    p = p[p.member]
    p.to_csv(a.out / "p13_atr_panel.csv", index=False)
    # Daily IC and quantiles.
    rows = []
    for d, g in p.groupby("date"):
        g = g.dropna(subset=["atr_pct", "ex20"])
        if len(g) < 50: continue
        q = pd.qcut(g.atr_pct.rank(method="first"), 5, labels=False)
        rows.append({"date": d, "n": len(g),
                     "ic20": stats.spearmanr(g.atr_pct, g.ex20).statistic,
                     "ic10": stats.spearmanr(g.atr_pct, g.ex10).statistic,
                     "ic5": stats.spearmanr(g.atr_pct, g.ex5).statistic,
                     "q5": g.ex20[q == 4].mean(), "q1": g.ex20[q == 0].mean(),
                     "spread20": g.ex20[q == 4].mean() - g.ex20[q == 0].mean(),
                     "spread5": g.ex5[q == 4].mean() - g.ex5[q == 0].mean(),
                     "spread10": g.ex10[q == 4].mean() - g.ex10[q == 0].mean()})
    daily = pd.DataFrame(rows)
    daily.to_csv(a.out / "p13_atr_daily_ic.csv", index=False)
    # 60/20/20 by date with 20-day purge at boundaries.
    dates = sorted(daily.date.unique()); c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
    train_end, val_end = dates[c1 - 1], dates[c2 - 1]
    purge = pd.Timedelta(days=35)
    seg = {"train": daily[daily.date <= train_end - purge], "validation": daily[(daily.date > train_end) & (daily.date <= val_end - purge)], "test": daily[daily.date > val_end]}
    oos = []
    for label, g in seg.items():
        oos.append({"segment": label, "dates": len(g), "start": str(g.date.min().date()), "end": str(g.date.max().date()),
                    "mean_ic20": g.ic20.mean(), "mean_spread20": g.spread20.mean(),
                    "hac_t20": hac_t(g.spread20), "p20": 2 * stats.t.sf(abs(hac_t(g.spread20)), len(g) - 1)})
    pd.DataFrame(oos).to_csv(a.out / "p13_atr_oos.csv", index=False)
    # BH on 3 horizons via HAC t.
    tests = []
    for h in (5, 10, 20):
        x = daily[f"spread{h}"].dropna(); t = hac_t(x); tests.append({"horizon": h, "mean_spread": x.mean(), "hac_t": t, "p": 2 * stats.t.sf(abs(t), len(x) - 1)})
    tdf = pd.DataFrame(tests); tdf["q"] = bh(tdf.p); tdf.to_csv(a.out / "p13_atr_hac.csv", index=False)
    # Quantile table 20D.
    qrows = []
    for d, g in p.dropna(subset=["atr_pct", "ex20"]).groupby("date"):
        if len(g) < 50: continue
        q = pd.qcut(g.atr_pct.rank(method="first"), 5, labels=False)
        for k in range(5): qrows.append({"date": d, "quantile": f"Q{k+1}", "ex20": g.ex20[q == k].mean()})
    pd.DataFrame(qrows).to_csv(a.out / "p13_atr_quantiles.csv", index=False)
    covs = []
    for d, g in p.groupby("date"):
        m = members_at(d)
        if m: covs.append(g.symbol.nunique() / len(m))
    coverage = {"start": str(dates[0].date()), "end": str(dates[-1].date()),
                "tickers": int(p.symbol.nunique()), "rows": int(len(p)),
                "membership_days": int(len(covs)),
                "member_day_coverage": float(np.mean(covs)) if covs else 0.0,
                "ticker_coverage": float(p.symbol.nunique() / max(len(set().union(*[members_at(d) for d in p.date.unique()])), 1)),
                "daily_obs_median": float(daily.n.median()),
                "price_fields": ["open", "high", "low", "close", "adjusted_close"],
                "atr_formula": "Wilder ATR(14)/close", "status": "EXPLORATORY_PIT_MEMBERSHIP_PARTIAL"}
    (a.out / "p13_data_readiness.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    (a.out / "p13_universe_audit.json").write_text(json.dumps({"membership_source": str(a.members), "tickers_with_prices": int(p.symbol.nunique()), "note": "daily membership applied; delisted/identity not independently verified"}, indent=2), encoding="utf-8")
    summary = {"coverage": coverage, "hac": tdf.to_dict("records"), "segments": oos,
               "price_basis": "ATR raw OHLC; returns adjusted_close", "portfolio": "NOT_RUN"}
    (a.out / "p13_manifest.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
