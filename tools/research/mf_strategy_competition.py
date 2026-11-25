#!/usr/bin/env python3
"""Multi-factor strategy competition V1: price and quality-limited backtests."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_mf_v1_out"); OUT.mkdir(parents=True, exist_ok=True)
SNAP = Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace/_us_research/data/_download/snap/research_factor_snapshots_sp500_pit_10y.csv")
FUND = Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace/_us_audit/pr512/data/universe/p7/updated_fundamentals.csv")
SPY = Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace/_us_audit/proxy_data/SPY.csv")
QQQ = Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace/_us_audit/proxy_data/QQQ.csv")
BIL = Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace/_us_p13/data/research/p9_1_support_resistance/bil.csv")


def z(s):
    s = s.astype(float); sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and np.isfinite(sd) else s * 0


def metrics(nav, ret, ppy=12):
    nav = nav.dropna(); ret = ret.dropna()
    if len(nav) < 2: return {}
    years = len(ret) / ppy
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1
    vol = ret.std() * np.sqrt(ppy)
    dd = nav / nav.cummax() - 1
    return {"CAGR": cagr, "Vol": vol, "Sharpe": cagr / vol if vol else None, "MaxDD": dd.min(),
            "Calmar": cagr / abs(dd.min()) if dd.min() else None, "Days": len(ret), "FinalNAV": nav.iloc[-1]}


snap = pd.read_csv(SNAP, usecols=["Technical_Date", "Ticker", "Price", "Momentum_20D_Pct", "Momentum_60D_Pct",
                                  "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
                                  "MA20", "MA50", "MA20_Slope_Pct_5D", "ATR_Pct"])
snap["Technical_Date"] = pd.to_datetime(snap.Technical_Date)
snap = snap[(snap.Technical_Date >= "2020-01-02") & (snap.Technical_Date <= "2024-12-31")].copy()
snap["ticker"] = snap.Ticker
snap.to_parquet(OUT / "price_features.parquet")
px = snap.pivot_table(index="Technical_Date", columns="Ticker", values="Price").sort_index()
px = px.ffill(limit=5)
fund = pd.read_csv(FUND, dtype={"ticker": str})
fund["ticker"] = fund.ticker.str.upper()
fund["roe"] = fund.net_income / fund.equity.replace(0, np.nan)
fund["fcf_margin"] = fund.fcf / fund.revenue.replace(0, np.nan)
fund["net_margin"] = fund.net_income / fund.revenue.replace(0, np.nan)
fund = fund.drop_duplicates("ticker").set_index("ticker")
quality = fund[["roe", "fcf_margin", "net_margin"]].dropna(how="all")

dates = list(px.index)
rebal = dates[::21]
rebal = [d for d in rebal if "2020-02-01" <= str(d.date()) <= "2024-12-31"]
spy = pd.read_csv(SPY); spy["Date"] = pd.to_datetime(spy.Date); spy = spy.set_index("Date").Close.sort_index()
qqq = pd.read_csv(QQQ); qqq["Date"] = pd.to_datetime(qqq.Date); qqq = qqq.set_index("Date").Close.sort_index()
bil = pd.read_csv(BIL); bil["Date"] = pd.to_datetime(bil.Date); bil = bil.set_index("Date").close.sort_index()


def run(kind):
    vals = [50000.0]; rets = []; turns = []; holdings = []
    prev = set()
    for i in range(len(rebal) - 1):
        d, nd = rebal[i], rebal[i + 1]
        g = snap[snap.Technical_Date == d].copy()
        g = g.dropna(subset=["Momentum_20D_Pct", "Momentum_60D_Pct", "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "Stock_RS_20D_vs_SPY"])
        if len(g) < 20: continue
        g["A"] = (z(g.Momentum_20D_Pct) + z(g.Momentum_60D_Pct) + z(g.Stock_RS_20D_vs_SPY)
                  + z(g.Volume_Ratio_20D) + z(g["MA20_Slope_Pct_5D"].fillna(0)) - z(g.Realized_Volatility_20D_Pct))
        g["B"] = g.Ticker.map(quality.roe).fillna(quality.roe.median()) * 0 + 0
        if kind == "B":
            q = quality.reindex(g.Ticker)
            g["score"] = z(q.roe.fillna(q.roe.median())) + z(q.fcf_margin.fillna(q.fcf_margin.median())) + z(q.net_margin.fillna(q.net_margin.median()))
        elif kind == "C":
            q = quality.reindex(g.Ticker)
            qs = z(q.roe.fillna(q.roe.median())) + z(q.fcf_margin.fillna(q.fcf_margin.median())) + z(q.net_margin.fillna(q.net_margin.median()))
            g["score"] = 0.6 * g.A + 0.4 * qs.values
        else:
            g["score"] = g.A
        top = g.nlargest(10, "score")
        tick = list(top.Ticker)
        r = px.loc[nd, tick] / px.loc[d, tick] - 1
        r = r.dropna()
        pr = r.mean() if len(r) else 0.0
        turnover = len(set(tick) - prev) / max(1, len(tick))
        cost = 0.0005 * (turnover + (1 if prev else 0))  # 5 bps one-way approximation
        pr -= cost
        vals.append(vals[-1] * (1 + pr)); rets.append(pr); turns.append(turnover); holdings.append(len(tick))
        prev = set(tick)
    nav = pd.Series(vals, index=[rebal[0]] + rebal[1:len(vals)])
    return nav, pd.Series(rets), float(np.mean(turns)) if turns else 0, np.mean(holdings) if holdings else 0


results = []; navs = {}
for k in ["A", "B", "C"]:
    nav, ret, turn, hold = run(k)
    m = metrics(nav, ret); m.update({"strategy": k, "turnover": turn, "avg_holdings": hold})
    results.append(m); navs[k] = nav

def bm(series, start, end):
    s = series[(series.index >= start) & (series.index <= end)].dropna()
    ret = s.pct_change().dropna(); nav = (1 + ret).cumprod() * 50000
    m = metrics(nav, ret, ppy=252); m["strategy"] = "bench"; return m
for name, s in [("SPY", spy), ("QQQ", qqq), ("BIL", bil)]:
    results.append({**bm(s, "2020-01-31", "2024-12-31"), "strategy": name, "turnover": 0, "avg_holdings": 0})
res = pd.DataFrame(results)
res.to_csv(OUT / "strategy_comparison.csv", index=False)
for k, nav in navs.items():
    nav.to_csv(OUT / f"nav_{k}.csv", header=["nav"])
summary = {"status": "DATA_LIMITED", "reason": "B/C use current fundamentals without PIT; price-only A valid but sample-limited; no full PIT universe",
           "strategies": res.to_dict("records")}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
print(res.to_string(index=False))


