#!/usr/bin/env python3
"""Multi-factor price strategy V2: daily close-to-close backtest, no look-ahead."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

COLS = ["Technical_Date", "Ticker", "Price", "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
        "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
        "MA20", "MA50", "MA20_Slope_Pct_5D", "ATR_Pct"]


def z(s):
    s = s.astype(float); sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and np.isfinite(sd) else s * 0


def metrics(nav, ret, ppy=252):
    nav = nav.dropna(); ret = ret.dropna()
    if len(nav) < 3: return {}
    years = len(ret) / ppy
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1
    vol = ret.std() * np.sqrt(ppy)
    dd = nav / nav.cummax() - 1
    downside = ret[ret < 0].std() * np.sqrt(ppy)
    return {"CAGR": cagr, "Vol": vol, "Sharpe": ret.mean() / ret.std() * np.sqrt(ppy) if ret.std() else None,
            "Sortino": ret.mean() / downside * np.sqrt(ppy) if downside else None,
            "MaxDD": dd.min(), "Calmar": cagr / abs(dd.min()) if dd.min() else None, "Days": len(ret)}


def backtest(feat, px, spy_close, start, end, mode="A", exit_mode="atr25", cost_bps=10, risk=0.005, maxpos=10, sig_by_date=None):
    dates = [d for d in px.index if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    if len(dates) < 30: return None
    spy = spy_close.reindex(dates).ffill(); ma200 = spy.rolling(200).mean(); regime = (spy > ma200)
    cash = 50000.0; holdings = {}; nav = []; trades = []; rets = []
    for i, d in enumerate(dates):
        if i == 0: nav.append(cash); continue
        prev = dates[i - 1]; pxd = px.loc[d]
        # exits based on previous close trigger, execute at current close
        for t in list(holdings):
            h = holdings[t]; p = pxd.get(t, np.nan)
            if not np.isfinite(p): continue
            trig = False; reason = ""
            if exit_mode in ("fixed6", "fixed8") and p <= h["stop"]:
                trig = True; reason = "STOP"
            if exit_mode in ("atr25", "atr20", "atr30") and p <= h["trail"]:
                trig = True; reason = "ATR_TRAIL"
            if exit_mode == "ma50":
                ma = sig_by_date.get(prev, pd.DataFrame()).get("MA50", pd.Series(dtype=float)).get(t, np.nan)
                if np.isfinite(ma) and p < ma: trig = True; reason = "MA50"
            if exit_mode == "rank":
                r = sig_by_date.get(prev, pd.DataFrame()).get("rank", pd.Series(dtype=float)).get(t, 999)
                if r > 20: trig = True; reason = "RANK"
            if h["days"] >= 20: trig = True; reason = "TIME"
            if trig:
                proceeds = h["shares"] * p * (1 - cost_bps / 1e4)
                cash += proceeds; trades.append({"ticker": t, "entry_date": h["entry_date"], "exit_date": str(d.date()),
                                                 "entry_price": h["entry"], "exit_price": p, "shares": h["shares"],
                                                 "exit_reason": reason, "pnl": (p - h["entry"]) * h["shares"] - 2 * cost_bps / 1e4 * h["entry"] * h["shares"]})
                del holdings[t]
        # entries from prior close signal, execute current close
        equity = cash + sum(h["shares"] * pxd.get(t, h["entry"]) for t, h in holdings.items())
        dd = equity / max(nav) - 1
        if i > 0 and regime.iloc[i - 1] and dd > -0.15 and len(holdings) < maxpos:
            g = sig_by_date.get(prev)
            if g is not None and len(g) > 20:
                cand = g.sort_values("score", ascending=False).head(maxpos - len(holdings))
                for t in cand.index:
                    if t in holdings: continue
                    p = pxd.get(t, np.nan); atr = cand.loc[t].get("ATR_Pct", np.nan)
                    if not np.isfinite(p) or p <= 0: continue
                    stopd = 0.08 if exit_mode in ("fixed6", "fixed8") else max(0.05, 2.5 * (atr or 3) / 100)
                    budget = min(equity * risk / stopd, equity * 0.10, cash * 0.95)
                    if budget < 500: continue
                    sh = budget / p; cash -= budget * (1 + cost_bps / 1e4)
                    holdings[t] = {"shares": sh, "entry": p, "entry_date": str(d.date()), "stop": p * (1 - stopd), "trail": p * (1 - stopd),
                                   "high": p, "days": 0}
        for t, h in holdings.items():
            p = pxd.get(t, h["entry"]); h["high"] = max(h["high"], p)
            h["trail"] = max(h["trail"], h["high"] * (1 - 2.5 * (sig_by_date.get(d, pd.DataFrame()).get("ATR_Pct", pd.Series(dtype=float)).get(t, 3)) / 100))
            h["days"] += 1
        eq = cash + sum(h["shares"] * pxd.get(t, h["entry"]) for t, h in holdings.items())
        nav.append(eq)
    n = pd.Series(nav, index=dates); r = n.pct_change().dropna()
    return {"nav": n, "ret": r, "metrics": metrics(n, r), "trades": pd.DataFrame(trades), "cash": cash}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--spy", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    snap = pd.read_csv(a.snapshot, usecols=COLS)
    snap["Technical_Date"] = pd.to_datetime(snap.Technical_Date)
    snap = snap.sort_values(["Technical_Date", "Ticker"]).drop_duplicates(["Technical_Date", "Ticker"])
    px = snap.pivot(index="Technical_Date", columns="Ticker", values="Price").sort_index().ffill(limit=5)
    feat = snap.set_index(["Technical_Date", "Ticker"])
    dates = px.index
    # scores per date
    rows = []
    for d, g in feat.groupby(level=0):
        g = g.droplevel(0).copy()
        if len(g) < 20: continue
        g["A"] = z(g.Momentum_20D_Pct) + z(g.Momentum_60D_Pct) + z(g.Stock_RS_20D_vs_SPY) + z(g.Volume_Ratio_20D) + z(g["MA20_Slope_Pct_5D"].fillna(0)) - z(g.Realized_Volatility_20D_Pct)
        g["B"] = z(g.Price / g.MA20 - 1) + z(g.Price / g.MA50 - 1) + z(g.Volume_Ratio_20D) + z(g.Stock_RS_20D_vs_SPY) - z(g.Realized_Volatility_20D_Pct)
        g["C"] = 0.6 * g.A + 0.3 * g.B
        g["rank"] = g.A.rank(ascending=False)
        rows.append(g[["A", "B", "C", "rank", "ATR_Pct", "MA20", "MA50"]])
    feat2 = pd.concat(rows, keys=[d for d in dates if d in set(snap.Technical_Date)])
    spy = pd.read_csv(a.spy); spy["Date"] = pd.to_datetime(spy.Date); spy = spy.set_index("Date").Close.sort_index()
    out = {"status": "NO_GO", "windows": {}, "exits": [], "comparison": []}
    sig = {d: feat2.xs(d) for d in feat2.index.get_level_values(0).unique()}
    for label, start in [("5Y", "2021-10-14")]:
        for mode, col in [("A", "A"), ("B", "B"), ("C", "C")]:
            f = feat2.copy(); f["score"] = f[col]
            r = backtest(f, px, spy, start, "2026-10-13", mode, "atr25", 10, sig_by_date=sig)
            if r:
                out["windows"][f"{label}_{mode}"] = r["metrics"]
                r["nav"].to_csv(a.out / f"nav_{label}_{mode}.csv", header=["nav"])
                if len(r["trades"]): r["trades"].to_csv(a.out / f"trades_{label}_{mode}.csv", index=False)
        # exit comparison on A 5Y
    f = feat2.copy(); f["score"] = f["A"]
    for ex in ["fixed6", "fixed8", "atr25", "ma50", "rank"]:
        r = backtest(f, px, spy, "2021-10-14", "2026-10-13", "A", ex, 10, sig_by_date=sig)
        if r: out["exits"].append({"exit": ex, **r["metrics"], "trades": len(r["trades"])})
    # cost sensitivity A 5Y
    for bps in [5, 10, 20]:
        r = backtest(f, px, spy, "2021-10-14", "2026-10-13", "A", "atr25", bps, sig_by_date=sig)
        if r: out["comparison"].append({"strategy": "A", "cost_bps": bps, **r["metrics"], "trades": len(r["trades"])})
    # benchmarks on same 5Y
    for name, path in [("SPY", a.spy)]:
        s = pd.read_csv(path); s["Date"] = pd.to_datetime(s.Date); s = s.set_index("Date").Close.sort_index()
        s = s[(s.index >= "2021-10-14") & (s.index <= "2026-10-13")].pct_change().dropna()
        nav = (1 + s).cumprod() * 50000
        out["comparison"].append({"strategy": name, "cost_bps": 0, **metrics(nav, s)})
    (a.out / "summary.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(out["exits"]).to_csv(a.out / "exit_comparison.csv", index=False)
    pd.DataFrame(out["comparison"]).to_csv(a.out / "comparison.csv", index=False)
    print(json.dumps(out["windows"], indent=2, default=str))


if __name__ == "__main__":
    main()


