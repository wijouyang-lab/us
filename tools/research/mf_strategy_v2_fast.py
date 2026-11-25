#!/usr/bin/env python3
"""Fast vectorized daily V2 engine: next-close execution, ledger, costs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

COLS = ["Technical_Date", "Ticker", "Price", "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
        "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "Stock_RS_20D_vs_SPY", "MA20", "MA50",
        "MA20_Slope_Pct_5D", "ATR_Pct"]


def z(s):
    sd = s.std(ddof=0); return (s - s.mean()) / sd if sd and np.isfinite(sd) else s * 0


def metrics(nav, ret, ppy=252):
    nav = np.asarray(nav); ret = np.asarray(ret)
    years = len(ret) / ppy; cagr = (nav[-1] / nav[0]) ** (1 / years) - 1
    vol = ret.std() * np.sqrt(ppy); dd = nav / np.maximum.accumulate(nav) - 1
    dn = ret[ret < 0].std() * np.sqrt(ppy)
    return {"CAGR": cagr, "Vol": vol, "Sharpe": ret.mean() / ret.std() * np.sqrt(ppy),
            "Sortino": ret.mean() / dn * np.sqrt(ppy) if dn else None, "MaxDD": dd.min(),
            "Calmar": cagr / abs(dd.min()) if dd.min() else None, "Days": len(ret)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--snapshot", type=Path, required=True); ap.add_argument("--spy", type=Path, required=True)
    ap.add_argument("--qqq", type=Path, required=True); ap.add_argument("--bil", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    snap = pd.read_csv(a.snapshot, usecols=COLS); snap["Technical_Date"] = pd.to_datetime(snap.Technical_Date)
    snap = snap.sort_values(["Technical_Date", "Ticker"]).drop_duplicates(["Technical_Date", "Ticker"])
    px = snap.pivot(index="Technical_Date", columns="Ticker", values="Price").sort_index().ffill(limit=5)
    dates = px.index; tickers = px.columns; n = len(tickers)
    scores = {k: pd.DataFrame(np.nan, index=dates, columns=tickers) for k in "ABC"}
    atr = pd.DataFrame(np.nan, index=dates, columns=tickers); ma50 = atr.copy()
    for d, g in snap.groupby("Technical_Date"):
        g = g.set_index("Ticker")
        A = z(g.Momentum_20D_Pct) + z(g.Momentum_60D_Pct) + z(g.Stock_RS_20D_vs_SPY) + z(g.Volume_Ratio_20D) + z(g["MA20_Slope_Pct_5D"].fillna(0)) - z(g.Realized_Volatility_20D_Pct)
        B = z(g.Price / g.MA20 - 1) + z(g.Price / g.MA50 - 1) + z(g.Volume_Ratio_20D) + z(g.Stock_RS_20D_vs_SPY) - z(g.Realized_Volatility_20D_Pct)
        scores["A"].loc[d, A.index] = A.values; scores["B"].loc[d, B.index] = B.values; scores["C"].loc[d, (0.6 * A + 0.4 * B).index] = (0.6 * A + 0.4 * B).values
        atr.loc[d, g.index] = g.ATR_Pct.values; ma50.loc[d, g.index] = g.MA50.values
    # ranks per score
    ranks = {k: scores[k].rank(axis=1, ascending=False) for k in "ABC"}
    pxv = px.values; atrv = atr.values; ma50v = ma50.values
    spy = pd.read_csv(a.spy); spy["Date"] = pd.to_datetime(spy.Date); spy = spy.set_index("Date").Close.sort_index()
    regime = (spy > spy.rolling(200).mean()).reindex(dates).ffill().values
    tix = {t: i for i, t in enumerate(tickers)}

    def run(score_key, start, end, exit_mode, bps):
        idx = [i for i, d in enumerate(dates) if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
        cash = 50000.0; holdings = {}; nav = []; rets = []; trades = []; maxpos = 10; total_cost = 0.0
        sv = scores[score_key].values; rv = ranks[score_key].values
        for j, i in enumerate(idx):
            if j == 0: nav.append(cash); continue
            p = pxv[i]; d = dates[i]; prev = i - 1
            # exits using previous close trigger, execute current close
            for ti in list(holdings):
                h = holdings[ti]; price = p[ti]; prevp = pxv[prev, ti]
                if not np.isfinite(price) or not np.isfinite(prevp): continue
                trig = False; reason = ""
                # trigger on PRIOR close, execute at CURRENT close
                if exit_mode in ("fixed6", "fixed8"):
                    if prevp <= h["stop"]: trig, reason = True, "STOP"
                elif exit_mode.startswith("atr"):
                    if prevp <= h["trail"]: trig, reason = True, "ATR_TRAIL"
                elif exit_mode == "ma50":
                    if np.isfinite(ma50v[prev, ti]) and prevp < ma50v[prev, ti]: trig, reason = True, "MA50"
                elif exit_mode == "rank20":
                    if rv[prev, ti] > 20: trig, reason = True, "RANK20"
                elif exit_mode == "time20":
                    if h["days"] >= 20: trig, reason = True, "TIME20"
                if trig:
                    gross = (price - h["entry"]) * h["sh"]
                    sell_fee = price * h["sh"] * bps / 1e4
                    net = gross - h["buy_fee"] - sell_fee
                    cash += price * h["sh"] - sell_fee; total_cost += sell_fee
                    trades.append({"ticker": tickers[ti], "signal_date": h["signal_date"], "entry_date": h["date"], "execution_date": str(d.date()),
                                   "exit_signal_date": str(dates[prev].date()), "exit_execution_date": str(d.date()),
                                   "entry_price": h["entry"], "exit_price": price, "shares": h["sh"], "buy_fee": h["buy_fee"],
                                   "sell_fee": sell_fee, "gross_pnl": gross, "pnl": net, "exit_reason": reason})
                    del holdings[ti]
            eq = cash + sum(h["sh"] * p[t] for t, h in holdings.items() if np.isfinite(p[t]))
            dd = eq / max(nav) - 1 if nav else 0
            if j > 0 and regime[prev] and dd > -0.15 and len(holdings) < maxpos:
                row = sv[prev]; order = np.argsort(-np.nan_to_num(row, nan=-1e9))[:30]
                for ti in order:
                    if ti in holdings or not np.isfinite(p[ti]) or not np.isfinite(atrv[prev, ti]): continue
                    mult = 0.06 if exit_mode == "fixed6" else 0.08 if exit_mode == "fixed8" else max(0.04, (float(exit_mode[3:]) / 10 if exit_mode.startswith("atr") else 2.5) * atrv[prev, ti] / 100)
                    budget = min(eq * 0.005 / mult, eq * 0.10, cash * 0.95)
                    if budget < 500: continue
                    sh = budget / p[ti]; cost = budget * bps / 1e4; cash -= budget + cost; total_cost += cost
                    holdings[ti] = {"sh": sh, "entry": p[ti], "date": str(d.date()), "signal_date": str(dates[prev].date()),
                                    "stop": p[ti] * (1 - mult), "trail": p[ti] * (1 - mult), "high": p[ti],
                                    "buy_fee": cost, "days": 0}
                    if len(holdings) >= maxpos: break
            for ti, h in holdings.items():
                if np.isfinite(p[ti]): h["high"] = max(h["high"], p[ti])
                if exit_mode.startswith("atr"):
                    mult = float(exit_mode[3:]) / 10
                    av = atrv[i, ti] if np.isfinite(atrv[i, ti]) else 30
                    h["trail"] = max(h["trail"], h["high"] * (1 - mult * av / 100))
                h["days"] += 1
            eq = cash + sum(h["sh"] * p[t] for t, h in holdings.items() if np.isfinite(p[t]))
            nav.append(eq); rets.append(eq / nav[-2] - 1 if len(nav) > 1 else 0)
        # open positions are not silently dropped
        lastp = pxv[idx[-1]]
        for ti, h in holdings.items():
            mark = lastp[ti] if np.isfinite(lastp[ti]) else h["entry"]
            trades.append({"ticker": tickers[ti], "signal_date": h["signal_date"], "entry_date": h["date"],
                           "execution_date": h["date"], "exit_signal_date": "", "exit_execution_date": "",
                           "entry_price": h["entry"], "exit_price": mark, "shares": h["sh"], "buy_fee": h["buy_fee"],
                           "sell_fee": 0.0, "gross_pnl": (mark - h["entry"]) * h["sh"],
                           "pnl": (mark - h["entry"]) * h["sh"] - h["buy_fee"], "exit_reason": "OPEN_AT_END"})
        return pd.Series(nav, index=[dates[i] for i in idx]), pd.DataFrame(trades), total_cost

    windows = {"5Y": "2021-10-14", "3Y": "2023-10-13", "1Y": "2025-10-13"}
    comp = []; exits = []; ledgers = []
    for w, start in windows.items():
        for k in "ABC":
            nav, tr, cost = run(k, start, "2026-10-13", "atr25", 10)
            m = metrics(nav.values, nav.pct_change().fillna(0).values[1:]); m.update({"strategy": k, "window": w, "cost": cost, "trades": len(tr)})
            comp.append(m); nav.to_csv(a.out / f"nav_{w}_{k}.csv", header=["nav"])
            if w == "5Y": tr.to_csv(a.out / f"trades_{w}_{k}.csv", index=False)
    for ex in ["fixed6", "fixed8", "atr20", "atr25", "atr30", "ma50", "rank20", "time20"]:
        nav, tr, cost = run("A", "2021-10-14", "2026-10-13", ex, 10)
        m = metrics(nav.values, nav.pct_change().fillna(0).values[1:]); m.update({"exit": ex, "trades": len(tr), "cost": cost})
        exits.append(m)
    for bps in [5, 10, 20]:
        nav, tr, cost = run("A", "2021-10-14", "2026-10-13", "atr25", bps)
        m = metrics(nav.values, nav.pct_change().fillna(0).values[1:]); m.update({"strategy": "A", "bps_per_side": bps, "trades": len(tr), "cost": cost})
        comp.append(m)
    # benchmarks
    for name, path in [("SPY", a.spy), ("QQQ", a.qqq), ("BIL", a.bil)]:
        s = pd.read_csv(path); dc = "Date" if "Date" in s else "date"; cc = "Close" if "Close" in s else "close"
        s[dc] = pd.to_datetime(s[dc]); s = s.set_index(dc)[cc].sort_index(); s = s[(s.index >= "2021-10-14") & (s.index <= "2026-10-13")].pct_change().dropna()
        nav = (1 + s).cumprod() * 50000; m = metrics(nav.values, s.values); m.update({"strategy": name, "window": "5Y", "trades": 0, "cost": 0})
        comp.append(m)
    pd.DataFrame(comp).to_csv(a.out / "comparison.csv", index=False); pd.DataFrame(exits).to_csv(a.out / "exit_comparison.csv", index=False)
    summary = {"status": "NO_GO", "windows": windows, "results": comp, "exits": exits,
               "data": {"snapshot": str(a.snapshot), "start": str(dates.min()), "end": str(dates.max()), "tickers": n, "dates": len(dates)}}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(pd.DataFrame(comp)[["strategy", "window", "CAGR", "Vol", "Sharpe", "MaxDD", "trades"]].to_string(index=False))


if __name__ == "__main__":
    main()

