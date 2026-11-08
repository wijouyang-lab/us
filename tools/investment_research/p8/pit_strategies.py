"""P8 Day-1/2: PIT S&P 500 technical strategy screen.

Reuses the repository's effective-dated S&P membership and raw price panel.
No current-index substitution. Missing prices are excluded, not filled.
"""
from __future__ import annotations
import argparse, json, math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(".")
MEMBERSHIP = ROOT / "data/research/historical_universe/sp500_daily.csv"
PRICES = ROOT / "data/research/pit_data/finsaber_prices_raw.csv"
OUT = ROOT / "data/research/p8"
OUT.mkdir(parents=True, exist_ok=True)
AS_OF = date(2024, 12, 31)
COST_BPS = 10.0
TOP_N = 20
OOS_START = date(2015, 1, 1)


def load_members():
    m = pd.read_csv(MEMBERSHIP)
    m["date"] = pd.to_datetime(m["date"]).dt.date
    m = m.drop_duplicates("date").sort_values("date")
    return m


def parse_members(s):
    return {x.strip().upper() for x in str(s).split(",") if x.strip()}


def monthly_dates(idx):
    s = pd.Series(idx, index=pd.to_datetime(idx))
    return list(s.groupby([s.index.year, s.index.month]).last().values)


def max_drawdown(equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    return float(dd.min()) if len(dd) else None


def hac_tstat(x, lags=6):
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    n = len(x)
    if n < 20: return None, None
    mu = x.mean(); e = x - mu
    gamma0 = float(np.dot(e, e) / n)
    var = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        g = float(np.dot(e[lag:], e[:-lag]) / n)
        var += 2 * (1 - lag / (lags + 1)) * g
    se = math.sqrt(max(var, 0) / n)
    t = mu / se if se else None
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2)))) if t is not None else None
    return t, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2000-01-03")
    ap.add_argument("--end", default="2024-12-31")
    a = ap.parse_args()
    px = pd.read_csv(PRICES, usecols=["date", "symbol", "open", "close", "adjusted_close"])
    px["date"] = pd.to_datetime(px["date"])
    px["symbol"] = px["symbol"].str.upper()
    px = px[(px.date >= a.start) & (px.date <= a.end)].copy()
    px["adj_open"] = px["open"] * (px["adjusted_close"] / px["close"])
    close = px.pivot_table(index="date", columns="symbol", values="adjusted_close", aggfunc="last")
    open_ = px.pivot_table(index="date", columns="symbol", values="adj_open", aggfunc="last")
    volume = px.pivot_table(index="date", columns="symbol", values="volume", aggfunc="last") if "volume" in px else None
    close = close.sort_index(); open_ = open_.reindex(close.index)
    # factors use close only, current/past
    mom20 = close / close.shift(20) - 1
    mom60 = close / close.shift(60) - 1
    mom120 = close / close.shift(120) - 1
    ma50 = close.rolling(50).mean(); ma200 = close.rolling(200).mean()
    vol60 = close.pct_change().rolling(60).std() * math.sqrt(252)
    rev5 = close / close.shift(5) - 1
    factors = {"MOMENTUM_20": mom20, "MOMENTUM_60": mom60, "MOMENTUM_120": mom120,
               "TREND_MA200": close / ma200 - 1, "LOW_VOL_60": -vol60, "REVERSAL_5": -rev5}
    m = load_members()
    mdates = list(m.date); mstrings = list(m.tickers)
    all_dates = list(close.index.date); date_index = {d: i for i, d in enumerate(all_dates)}
    month_ends = [d for d in monthly_dates(all_dates) if date.fromisoformat(str(d)) <= AS_OF]
    returns = {k: [] for k in factors}; ew = []; dates = []; cover = []
    prev_hold = {k: set() for k in factors}
    for mi, md in enumerate(month_ends[:-1]):
        # membership effective on the formation date
        pos = np.searchsorted(mdates, md, side="right") - 1
        if pos < 0: continue
        members = parse_members(mstrings[pos])
        di = date_index.get(md)
        if di is None or di + 1 >= len(all_dates): continue
        entry_date = all_dates[di + 1]
        exit_month = month_ends[mi + 1]
        # exit at first session of next month after its formation? use next month end entry
        next_di = date_index.get(month_ends[mi + 1])
        if next_di is None or next_di + 1 >= len(all_dates): continue
        exit_date = all_dates[next_di + 1]
        cols = [c for c in close.columns if c in members]
        avail = [c for c in cols if pd.notna(close.loc[pd.Timestamp(md), c]) and pd.notna(open_.loc[pd.Timestamp(entry_date), c]) and pd.notna(open_.loc[pd.Timestamp(exit_date), c])]
        cover.append(len(avail) / len(cols) if cols else 0)
        if len(avail) < 30: continue
        dates.append(md.isoformat())
        ew.append(float(np.mean([open_.loc[pd.Timestamp(exit_date), c] / open_.loc[pd.Timestamp(entry_date), c] - 1 for c in avail])))
        for name, f in factors.items():
            vals = [(c, f.loc[pd.Timestamp(md), c]) for c in avail if pd.notna(f.loc[pd.Timestamp(md), c])]
            vals = [(c, x) for c, x in vals if np.isfinite(x)]
            vals.sort(key=lambda z: -z[1])
            hold = {c for c, _ in vals[:TOP_N]}
            if not hold: returns[name].append(None); continue
            gross = float(np.mean([open_.loc[pd.Timestamp(exit_date), c] / open_.loc[pd.Timestamp(entry_date), c] - 1 for c in hold]))
            turn = len(hold ^ prev_hold[name]) / max(len(hold), 1)
            net = gross - COST_BPS / 10000.0 * turn * 2.0
            returns[name].append(net)
            prev_hold[name] = hold
    # Equal weight benchmark aligned to exactly the same months.
    ew = [x for x in ew if x is not None]
    dates_for_ew = dates[:len(ew)]
    results = {}
    for name, xs in returns.items():
        vals = [(d, x) for d, x in zip(dates, xs) if x is not None]
        if not vals: continue
        ds = [x[0] for x in vals]; r = np.array([x[1] for x in vals], dtype=float)
        eq = np.cumprod(1 + r); years = len(r) / 12
        cagr = eq[-1] ** (1 / years) - 1 if years > 0 and eq[-1] > 0 else None
        vol = float(r.std(ddof=1) * math.sqrt(12))
        sharpe = float(r.mean() / r.std(ddof=1) * math.sqrt(12)) if r.std(ddof=1) > 0 else None
        oos = np.array([x for d, x in vals if date.fromisoformat(d) >= OOS_START])
        oos_cagr = (np.cumprod(1 + oos)[-1] ** (12 / len(oos)) - 1) if len(oos) else None
        oos_sharpe = float(oos.mean() / oos.std(ddof=1) * math.sqrt(12)) if len(oos) > 1 and oos.std(ddof=1) > 0 else None
        # excess vs EW for months present
        ew_map = dict(zip(dates_for_ew, ew))
        ex = np.array([x - ew_map[d] for d, x in vals if d in ew_map])
        t, p = hac_tstat(ex, 6)
        results[name] = {"months": len(r), "cagr_net": cagr, "vol": vol, "sharpe": sharpe,
                         "max_drawdown": max_drawdown(eq), "oos_months": len(oos),
                         "oos_cagr_net": oos_cagr, "oos_sharpe": oos_sharpe,
                         "excess_mean_monthly": float(ex.mean()) if len(ex) else None,
                         "hac_t": t, "p_value": p, "avg_coverage": float(np.mean(cover)) if cover else None,
                         "dates": [ds[0], ds[-1]]}
    # EW full metrics and OOS
    r = np.array(ew)
    eq = np.cumprod(1 + r); years = len(r) / 12
    oos = np.array([x for d, x in zip(dates_for_ew, ew) if date.fromisoformat(d) >= OOS_START])
    ew_res = {"months": len(r), "cagr_net": float(eq[-1] ** (1 / years) - 1), "vol": float(r.std(ddof=1) * math.sqrt(12)),
              "sharpe": float(r.mean() / r.std(ddof=1) * math.sqrt(12)), "max_drawdown": max_drawdown(eq),
              "oos_months": len(oos), "oos_cagr_net": float(np.cumprod(1 + oos)[-1] ** (12 / len(oos)) - 1),
              "oos_sharpe": float(oos.mean() / oos.std(ddof=1) * math.sqrt(12)),
              "dates": [dates_for_ew[0], dates_for_ew[-1]]}
    # BH multiple testing across six strategy p-values (exclude EW).
    ps = [(k, v["p_value"]) for k, v in results.items() if v["p_value"] is not None]
    ps.sort(key=lambda x: x[1]); mtest = len(ps)
    qvals = {}
    for rank, (k, p) in enumerate(ps, 1): qvals[k] = min(1.0, p * mtest / rank)
    for k, v in results.items():
        q = qvals.get(k)
        v["bh_q"] = q
        v["gate"] = "GO" if (v["hac_t"] or 0) >= 1.64 and (q or 1) <= 0.10 and (v["oos_cagr_net"] or -1) > ew_res["oos_cagr_net"] and (v["max_drawdown"] or -1) >= -0.35 else "NO-GO"
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": AS_OF.isoformat(),
              "universe": "S&P 500 effective-dated membership", "membership_source": str(MEMBERSHIP),
              "price_source": str(PRICES), "price_range": [a.start, a.end],
              "method": "month-end signal; next-session open entry; next month next-session open exit; top20 equal weight; 10bps per side",
              "coverage_mean": float(np.mean(cover)) if cover else None,
              "benchmark_equal_weight": ew_res, "strategies": results,
              "multiple_testing": {"method": "Benjamini-Hochberg", "hypotheses": mtest, "q_values": qvals},
              "status": "PIT_PRELIMINARY_RESEARCH", "note": "No current Nasdaq-100/Dow membership source; not substituted. Historical PIT uses S&P only."}
    (OUT / "pit_strategy_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"coverage_mean": report["coverage_mean"], "benchmark": ew_res,
                      "strategies": {k: {"cagr": v["cagr_net"], "oos_cagr": v["oos_cagr_net"], "sharpe": v["sharpe"],
                                         "oos_sharpe": v["oos_sharpe"], "hac_t": v["hac_t"], "q": v["bh_q"], "gate": v["gate"]}
                                     for k, v in results.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
