#!/usr/bin/env python3
"""P16 multifactor entry/exit portfolio research, offline only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", type=Path, required=True)
    ap.add_argument("--members", type=Path, required=True)
    ap.add_argument("--spy", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(a.prices, usecols=["date", "symbol", "close", "adjusted_close"])
    raw["date"] = pd.to_datetime(raw.date)
    raw = raw.drop_duplicates(["symbol", "date"]).dropna()
    mat = raw.pivot(index="date", columns="symbol", values="adjusted_close").sort_index()
    rets = mat.pct_change()
    val = mat.ffill()  # valuation marks only; signals/trades still require actual prices
    dates = pd.DatetimeIndex(mat.index)
    # factors use all history; signals restricted to 2020-2024
    mom63 = mat / mat.shift(63) - 1
    mom126 = mat / mat.shift(126) - 1
    sma50 = mat.rolling(50).mean(); sma200 = mat.rolling(200).mean()
    vol20 = rets.rolling(20).std() * np.sqrt(252)
    vol252med = vol20.rolling(252, min_periods=100).median()
    fwd21 = mat.shift(-22) / mat.shift(-1) - 1
    spy = pd.read_csv(a.spy, usecols=["Date", "close"]); spy["date"] = pd.to_datetime(spy.Date, utc=True).dt.tz_convert(None).dt.normalize()
    spy = spy.set_index("date")["close"].sort_index().reindex(dates).ffill()
    regime = spy > spy.rolling(200).mean()
    mem = pd.read_csv(a.members); mem["date"] = pd.to_datetime(mem.date)
    snap = list(mem.date); mm = {d: set(str(t).split(",")) for d, t in zip(mem.date, mem.tickers)}
    import bisect
    def members_at(d):
        i = bisect.bisect_right(snap, d) - 1
        return mm.get(snap[i], set()) if i >= 0 else set()
    start = pd.Timestamp("2020-01-02")
    # Daily IC of trend score, no portfolio.
    ic_rows = []
    for i, d in enumerate(dates):
        if d < start or i < 126 or i + 22 >= len(dates): continue
        s = set(members_at(d))
        g = pd.DataFrame({"ticker": list(s)})
        g["m63"] = g.ticker.map(mom63.loc[d]); g["m126"] = g.ticker.map(mom126.loc[d])
        g["fwd"] = g.ticker.map(fwd21.loc[d])
        g = g.dropna()
        if len(g) < 50: continue
        g["score"] = .5 * g.m63.rank(pct=True) + .5 * g.m126.rank(pct=True)
        q = pd.qcut(g.score.rank(method="first"), 5, labels=False)
        ic_rows.append({"date": d, "n": len(g), "ic": stats.spearmanr(g.score, g.fwd).statistic,
                        "q1": g.fwd[q == 0].mean(), "q5": g.fwd[q == 4].mean()})
    ic = pd.DataFrame(ic_rows); ic["spread"] = ic.q5 - ic.q1
    ic.to_csv(a.out / "p16_entry_ic.csv", index=False)
    # Portfolio simulation helper.
    def simulate(exit_mode, use_regime, cost_bps):
        cash = 50000.0; holdings = {}; nav = []
        maxpos = 10
        for i, d in enumerate(dates):
            if d < start or i < 200: continue
            equity_prev = cash + sum(h["shares"] * val.at[d, t] for t, h in holdings.items() if pd.notna(val.at[d, t]))
            # exits based on prior close i-1 trigger, execute current close
            for t in list(holdings):
                h = holdings[t]; px = mat.at[d, t]
                if pd.isna(px): continue
                trig = h["days"] >= 21
                if exit_mode in ("trend", "both") and pd.notna(sma50.loc[dates[i - 1], t]):
                    trig = trig or mat.iloc[i - 1][t] < sma50.iloc[i - 1][t]
                if exit_mode in ("risk", "both") and pd.notna(vol20.loc[dates[i - 1], t]) and pd.notna(vol252med.loc[dates[i - 1], t]):
                    trig = trig or vol20.iloc[i - 1][t] > 2 * vol252med.iloc[i - 1][t]
                if trig:
                    proceeds = h["shares"] * px * (1 - cost_bps / 1e4)
                    cash += proceeds; del holdings[t]
            # entries based on prior close signal, execute current close
            if (not use_regime) or bool(regime.iloc[i - 1]):
                if len(holdings) < maxpos:
                    pd_ = dates[i - 1]; s = set(members_at(pd_))
                    cand = []
                    for t in s:
                        if t in holdings or t not in mat.columns: continue
                        p = mat.at[pd_, t]
                        if pd.isna(p) or pd.isna(mom63.at[pd_, t]) or pd.isna(mom126.at[pd_, t]): continue
                        if pd.isna(mat.at[d, t]): continue
                        cand.append((t, .5 * mom63.at[pd_, t] + .5 * mom126.at[pd_, t]))
                    cand.sort(key=lambda x: x[1], reverse=True)
                    for t, _ in cand[:maxpos - len(holdings)]:
                        px = mat.at[d, t]
                        alloc = min(equity_prev / maxpos, cash / (1 + cost_bps / 1e4))
                        if alloc <= 100: break
                        shares = alloc / px
                        cash -= alloc * (1 + cost_bps / 1e4)
                        holdings[t] = {"shares": shares, "days": 0}
            for t in holdings: holdings[t]["days"] += 1
            eq = cash + sum(h["shares"] * val.at[d, t] for t, h in holdings.items() if pd.notna(val.at[d, t]))
            nav.append({"date": d, "nav": eq, "cash": cash, "positions": len(holdings)})
        n = pd.DataFrame(nav); n["ret"] = n.nav.pct_change().fillna(0); n["dd"] = n.nav / n.nav.cummax() - 1
        return n
    variants = {}
    for mode in ("time", "trend", "risk", "both"):
        for regime_on in (False, True):
            for bps in (5, 10, 20):
                label = f"{mode}_{'regime' if regime_on else 'noreg'}_{bps}"
                n = simulate(mode, regime_on, bps)
                r = n.ret; ann = (n.nav.iloc[-1] / 50000) ** (252 / len(n)) - 1 if len(n) else np.nan
                variants[label] = {"periods": len(n), "final_nav": float(n.nav.iloc[-1]), "cagr": float(ann),
                                   "vol": float(r.std() * np.sqrt(252)), "sharpe": float(ann / (r.std() * np.sqrt(252))) if r.std() else None,
                                   "max_dd": float(n.dd.min()), "avg_positions": float(n.positions.mean()),
                                   "cost_bps": bps, "exit": mode, "regime": regime_on}
                n.to_csv(a.out / f"p16_nav_{label}.csv", index=False)
    summary = {"entry": {"dates": len(ic), "mean_ic": float(ic.ic.mean()), "mean_spread": float(ic.spread.mean()),
                         "hac_t": float(ic.spread.mean() / (ic.spread.std(ddof=1) / np.sqrt(len(ic)))) if len(ic) > 1 else None},
               "variants": variants, "regime_days": int(regime.sum()), "regime_all": int(regime.notna().sum())}
    (a.out / "p16_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
