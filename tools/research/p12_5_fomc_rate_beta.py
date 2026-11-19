#!/usr/bin/env python3
"""P12.5 FOMC rate-sensitivity cross-sectional research.

Uses only local snapshot and ETF prices. No network, no model, no orders.
Signal is computed before the event; returns are measured after the event close.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def load_prices(snapshot: Path):
    df = pd.read_csv(snapshot, usecols=["Technical_Date", "Ticker", "Price"])
    df["date"] = pd.to_datetime(df["Technical_Date"])
    df = df.dropna(subset=["date", "Price"]).drop_duplicates(["date", "Ticker"])
    return df.pivot(index="date", columns="Ticker", values="Price").sort_index()


def load_etf(path: Path):
    df = pd.read_csv(path, usecols=["Date", "Adj Close"])
    df["date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_convert(None).dt.normalize()
    return df.set_index("date")["Adj Close"].sort_index()


def beta(stock: pd.Series, spy: pd.Series, tlt: pd.Series, end, window, min_obs):
    idx = stock.index[stock.index <= end]
    if len(idx) < min_obs + 1:
        return None
    idx = idx[-(window + 1):]
    r = pd.concat([stock.pct_change(), spy.pct_change(), tlt.pct_change()], axis=1, join="inner").dropna()
    r = r[r.index <= end].tail(window)
    if len(r) < min_obs:
        return None
    X = np.column_stack([np.ones(len(r)), r.iloc[:, 1], r.iloc[:, 2]])
    y = r.iloc[:, 0].to_numpy()
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(coef[1]), float(coef[2])


def fwd_excess(stock: pd.Series, spy: pd.Series, t0, horizon):
    idx = stock.index[stock.index >= t0]
    if len(idx) < horizon + 1:
        return None
    s0, s1 = idx[0], idx[horizon]
    sidx = spy.index[spy.index >= t0]
    if len(sidx) < horizon + 1:
        return None
    m0, m1 = sidx[0], sidx[horizon]
    return (stock[s1] / stock[s0] - 1) - (spy[m1] / spy[m0] - 1)


def bh(pvalues):
    n = len(pvalues)
    order = np.argsort(pvalues)
    q = np.empty(n)
    prev = 1.0
    for rank in range(n - 1, -1, -1):
        i = order[rank]
        prev = min(prev, pvalues[i] * n / (rank + 1))
        q[i] = prev
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--spy", type=Path, required=True)
    ap.add_argument("--tlt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    prices = load_prices(args.snapshot)
    spy = load_etf(args.spy)
    tlt = load_etf(args.tlt)
    ev = pd.read_csv(args.events)
    ev = ev[(ev.event_type == "fomc") & ev.tradable_session.notna()].copy()
    ev["pub"] = pd.to_datetime(ev.publication_date)
    ev["session"] = pd.to_datetime(ev.tradable_session)
    sessions = pd.DatetimeIndex(sorted(set(spy.index)))
    spy = spy.reindex(sessions).ffill()
    tlt = tlt.reindex(sessions).ffill()
    tickers = [c for c in prices.columns if c not in ("SPY", "TLT")]
    rows = []
    for _, e in ev.iterrows():
        pre = prices.index[prices.index < e.pub]
        if len(pre) < 252:
            continue
        signal = pre[-1]
        day_idx = sessions[sessions >= e.session]
        if len(day_idx) < 21:
            continue
        t0 = day_idx[0]
        tlt_prev = tlt[tlt.index < t0]
        spy_prev = spy[spy.index < t0]
        if tlt_prev.empty or spy_prev.empty:
            continue
        tlt_ret = tlt.asof(t0) / tlt_prev.iloc[-1] - 1
        spy_ret = spy.asof(t0) / spy_prev.iloc[-1] - 1
        for ticker in tickers:
            s = prices[ticker].dropna()
            b = beta(s, spy, tlt, signal, 252, 180)
            if b is None:
                continue
            fwd = {h: fwd_excess(s, spy, t0, h) for h in (1, 5, 10, 20)}
            if any(v is None for v in fwd.values()):
                continue
            rows.append({"event_id": e.event_id, "date": e.publication_date, "ticker": ticker,
                         "signal_date": signal.date().isoformat(), "beta_spy": b[0], "beta_tlt": b[1],
                         "tlt_event": tlt_ret, "spy_event": spy_ret,
                         "vol20": s.pct_change().tail(20).std() * np.sqrt(252),
                         "mom20": s.iloc[-1] / s.iloc[-21] - 1 if len(s) > 21 else np.nan,
                         **{f"fwd{h}": v for h, v in fwd.items()}})
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise SystemExit("no observations")
    # Cross-sectional standardized controls within event.
    for col in ("beta_tlt", "beta_spy", "vol20", "mom20"):
        panel[col + "_z"] = panel.groupby("event_id")[col].transform(lambda x: (x - x.mean()) / x.std(ddof=0))
    results = []
    for h in (1, 5, 10, 20):
        y = f"fwd{h}"
        for name, x in (("beta_tlt", "beta_tlt"), ("beta_tlt_z", "beta_tlt_z"), ("beta_spy", "beta_spy")):
            ics = []
            spreads = []
            for eid, g in panel.groupby("event_id"):
                g = g.dropna(subset=[x, y])
                if len(g) < 20:
                    continue
                ic = stats.spearmanr(g[x], g[y]).statistic
                if np.isfinite(ic):
                    ics.append(ic)
                q = pd.qcut(g[x].rank(method="first"), 5, labels=False)
                top, bot = g[y][q == 4].mean(), g[y][q == 0].mean()
                spreads.append(top - bot)
            if len(ics) < 3:
                continue
            ics, spreads = np.array(ics), np.array(spreads)
            t_ic = stats.ttest_1samp(ics, 0).statistic
            p_ic = stats.ttest_1samp(ics, 0).pvalue
            t_sp = stats.ttest_1samp(spreads, 0).statistic
            p_sp = stats.ttest_1samp(spreads, 0).pvalue
            results.append({"horizon": h, "feature": name, "events": len(ics), "mean_ic": ics.mean(),
                            "ic_t": t_ic, "ic_p": p_ic, "mean_spread": spreads.mean(),
                            "spread_t": t_sp, "spread_p": p_sp,
                            "spread_ci_low": spreads.mean() - 1.96 * spreads.std(ddof=1) / np.sqrt(len(spreads)),
                            "spread_ci_high": spreads.mean() + 1.96 * spreads.std(ddof=1) / np.sqrt(len(spreads))})
    res = pd.DataFrame(results)
    if not res.empty:
        res["ic_q"] = bh(res.ic_p.to_numpy())
        res["spread_q"] = bh(res.spread_p.to_numpy())
    # OOS split by event order, using beta_tlt only; 60/20/20.
    event_ids = sorted(panel.event_id.unique())
    cut1, cut2 = int(len(event_ids) * .6), int(len(event_ids) * .8)
    train, valid, test = set(event_ids[:cut1]), set(event_ids[cut1:cut2]), set(event_ids[cut2:])
    oos = []
    for label, ids in (("train", train), ("validation", valid), ("test", test)):
        for h in (1, 5, 10, 20):
            g = panel[panel.event_id.isin(ids)].dropna(subset=["beta_tlt", "fwd%d" % h])
            ics = []
            for eid, gg in g.groupby("event_id"):
                if len(gg) >= 20:
                    ics.append(stats.spearmanr(gg.beta_tlt, gg["fwd%d" % h]).statistic)
            if ics:
                oos.append({"split": label, "horizon": h, "events": len(ics), "mean_ic": float(np.mean(ics))})
    pd.DataFrame(oos).to_csv(args.out / "oos_ic.csv", index=False)
    panel.to_csv(args.out / "fomc_rate_beta_panel.csv", index=False)
    res.to_csv(args.out / "event_results.csv", index=False)
    summary = {"events": int(panel.event_id.nunique()), "observations": int(len(panel)),
               "tickers": int(panel.ticker.nunique()), "signal_window": 252,
               "min_obs": 180, "horizons": [1, 5, 10, 20],
               "event_range": [panel.date.min(), panel.date.max()],
               "tests": len(res), "oos": oos,
               "note": "FOMC only; BLS CPI/Employment precise publication times unavailable. Close-to-close proxy, unadjusted Price."}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
