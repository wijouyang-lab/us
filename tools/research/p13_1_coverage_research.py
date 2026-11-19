#!/usr/bin/env python3
"""P13.1 coverage-driven universe audit and exploratory price-behaviour study."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

OUT = Path("data/research/p13_1")
OUT.mkdir(parents=True, exist_ok=True)
PRICES = Path("../_us_audit/pr512/data/research/pit_data/finsaber_prices_raw.csv")
MEMBERS = Path("../_us_audit/pr512/data/research/historical_universe/sp500_daily.csv")
SPY = Path("../_us_audit/pr512/data/research/p9_1_support_resistance/SPY.csv")


def nw(x, lag=4):
    x = np.asarray(x, float); n = len(x); e = x - x.mean(); v = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(v / n) if v > 0 else np.nan


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); q = np.empty(n); prev = 1.0
    for rank in range(n - 1, -1, -1):
        i = o[rank]; prev = min(prev, p[i] * n / (rank + 1)); q[i] = prev
    return q


raw = pd.read_csv(PRICES, usecols=["date", "symbol", "close", "adjusted_close"])
raw["date"] = pd.to_datetime(raw.date)
raw = raw.dropna().sort_values(["symbol", "date"])
raw["ret"] = raw.groupby("symbol").adjusted_close.pct_change()
raw["vol20"] = raw.groupby("symbol").ret.transform(lambda x: x.rolling(20, min_periods=20).std() * np.sqrt(252))
raw["mom20"] = raw.groupby("symbol").adjusted_close.transform(lambda x: x / x.shift(20) - 1)
raw["fwd20"] = raw.groupby("symbol").adjusted_close.shift(-20) / raw.adjusted_close - 1
spy = pd.read_csv(SPY, usecols=["Date", "close"]); spy["date"] = pd.to_datetime(spy.Date, utc=True).dt.tz_convert(None).dt.normalize()
spy = spy.set_index("date")["close"].sort_index()
raw["spy20"] = raw.date.map(spy.shift(-20) / spy - 1)
raw["ex20"] = raw.fwd20 - raw.spy20

mem = pd.read_csv(MEMBERS); mem["date"] = pd.to_datetime(mem.date)
snap = sorted(set(mem.date)); mm = {d: set(str(t).split(",")) for d, t in zip(mem.date, mem.tickers)}
import bisect
def members_at(d):
    i = bisect.bisect_right(snap, d) - 1
    return mm.get(snap[i], set()) if i >= 0 else set()

rows = []
for start, end, label in [("2020-01-01", "2024-12-31", "5Y"), ("2022-01-01", "2024-12-31", "3Y")]:
    p = raw[(raw.date >= start) & (raw.date <= end)].copy()
    p = p[p.apply(lambda r: r.symbol in members_at(r.date), axis=1)]
    expected = 0; observed = 0
    for d, g in p.groupby("date"):
        expected += len(members_at(d)); observed += g.symbol.nunique()
    # per-stock coverage over member days
    stock_cov = []
    for sym, g in p.groupby("symbol"):
        md = sum(1 for d in g.date if sym in members_at(d))
        stock_cov.append((sym, md, len(g)))
    stock = pd.DataFrame(stock_cov, columns=["ticker", "member_days", "observed_days"])
    stock["coverage"] = stock.observed_days / stock.member_days.replace(0, np.nan)
    pools = {"broad": stock[stock.member_days >= 20],
             "cover80": stock[stock.coverage >= .80],
             "cover95": stock[stock.coverage >= .95],
             "continuous": stock[stock.coverage >= .95]}
    rows.append({"window": label, "start": str(p.date.min().date()), "end": str(p.date.max().date()),
                 "expected_member_days": expected, "observed_member_days": observed,
                 "member_day_coverage": observed / expected if expected else 0,
                 "tickers": int(stock.ticker.nunique()), "median_names": float(p.groupby("date").size().median()),
                 "pools": {k: int(len(v)) for k, v in pools.items()},
                 "stock_coverage_median": float(stock.coverage.median()),
                 "stock_coverage_80": int((stock.coverage >= .8).sum()),
                 "stock_coverage_95": int((stock.coverage >= .95).sum())})
    if label == "5Y":
        p5 = p
        stock5 = stock

(OUT / "p13_1_coverage.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
stock5.to_csv(OUT / "p13_1_stock_coverage.csv", index=False)

# Price behaviour: daily IC and Q5-Q1 for vol20 and mom20, 20D excess.
p = p5.dropna(subset=["vol20", "mom20", "ex20"])
daily = []
for d, g in p.groupby("date"):
    if len(g) < 50: continue
    row = {"date": d, "n": len(g)}
    for f in ("vol20", "mom20"):
        row[f"ic_{f}"] = stats.spearmanr(g[f], g.ex20).statistic
        q = pd.qcut(g[f].rank(method="first"), 5, labels=False)
        row[f"spread_{f}"] = g.ex20[q == 4].mean() - g.ex20[q == 0].mean()
        row[f"low_minus_high_{f}"] = g.ex20[q == 0].mean() - g.ex20[q == 4].mean()
    daily.append(row)
d = pd.DataFrame(daily); d.to_csv(OUT / "p13_1_price_daily.csv", index=False)
res = []
for f in ("vol20", "mom20"):
    for prefix, col in (("high_minus_low", f"spread_{f}"), ("low_minus_high", f"low_minus_high_{f}")):
        x = d[col].dropna(); t = nw(x); res.append({"factor": f, "direction": prefix, "mean": x.mean(), "hac_t": t,
                                                     "p": 2 * stats.t.sf(abs(t), len(x) - 1), "dates": len(x),
                                                     "mean_ic": d[f"ic_{f}"].mean()})
r = pd.DataFrame(res); r["q"] = bh(r.p); r.to_csv(OUT / "p13_1_price_hac.csv", index=False)
# OOS 60/20/20 by date.
dates = sorted(d.date.unique()); c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
oos = []
for label, ds in (("train", dates[:c1]), ("validation", dates[c1:c2]), ("test", dates[c2:])):
    g = d[d.date.isin(ds)]
    for f in ("vol20", "mom20"):
        oos.append({"segment": label, "factor": f, "dates": len(g), "mean_ic": g[f"ic_{f}"].mean(),
                    "high_minus_low": g[f"spread_{f}"].mean(), "low_minus_high": g[f"low_minus_high_{f}"].mean()})
pd.DataFrame(oos).to_csv(OUT / "p13_1_price_oos.csv", index=False)
summary = {"coverage": rows, "price": r.to_dict("records"), "oos": oos,
           "coverage_thresholds": {"member_day_95": all(x["member_day_coverage"] >= .95 for x in rows)},
           "note": "ADJUSTMENT_UNVERIFIED adjusted_close; ATR not retested"}
(OUT / "p13_1_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
print(json.dumps(summary, indent=2, default=str))
