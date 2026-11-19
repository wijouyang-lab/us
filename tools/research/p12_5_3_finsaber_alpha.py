#!/usr/bin/env python3
"""P12.5.3 FINSABER adjusted-price exploratory CPI/Employment pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tools.research.p12_5_3_macro_equity_alpha import METRICS, PRIMARY, beta, fwd, z_dev, bh


def load_prices(path):
    df = pd.read_csv(path, usecols=["date", "symbol", "adjusted_close"])
    df["date"] = pd.to_datetime(df.date)
    return df.dropna().drop_duplicates(["date", "symbol"]).pivot(index="date", columns="symbol", values="adjusted_close").sort_index()


def load_etf(path):
    df = pd.read_csv(path, usecols=["Date", "Adj Close"])
    df["date"] = pd.to_datetime(df.Date, utc=True).dt.tz_convert(None).dt.normalize()
    return df.set_index("date")["Adj Close"].sort_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    for name in ("spy", "tlt", "gld", "iwm"):
        ap.add_argument(f"--{name}", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    prices = load_prices(a.prices)
    spy = load_etf(a.spy); sessions = spy.index
    etfs = {k: load_etf(getattr(a, k)).reindex(sessions).ffill() for k in ("tlt", "gld", "iwm")}
    ev_all = pd.read_csv(a.events); ev_all["release_date"] = pd.to_datetime(ev_all.release_date)
    ev = ev_all[(ev_all.release_date >= "2017-01-01") & (ev_all.release_date <= "2024-12-31")].copy()
    rows = []
    for _, e in ev.iterrows():
        pre = prices.index[prices.index < e.release_date]
        post = sessions[sessions > e.release_date]
        if len(pre) < 252 or len(post) < 21:
            continue
        signal, entry = pre[-1], post[0]
        for ticker in prices.columns:
            s = prices[ticker].dropna()
            b = beta(s, spy, etfs["tlt"], etfs["gld"], etfs["iwm"], signal)
            if b is None:
                continue
            f = {h: fwd(s, spy, entry, h) for h in (1, 5, 10, 20)}
            if any(v is None for v in f.values()):
                continue
            rows.append({"event_id": e.event_id, "event_type": e.event_type, "release_date": e.release_date,
                         "ticker": ticker, "entry": entry, **b, **{f"fwd{h}": v for h, v in f.items()}})
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise SystemExit("no observations")
    evz = ev_all.copy()
    for fam, metrics in METRICS.items():
        g = evz[evz.event_type == fam].sort_values("release_date").copy()
        for m in metrics:
            g[m + "_z"] = z_dev(pd.to_numeric(g[m], errors="coerce"))
        evz.loc[g.index, [m + "_z" for m in metrics]] = g[[m + "_z" for m in metrics]]
    panel = panel.merge(evz[["event_id"] + [m + "_z" for ms in METRICS.values() for m in ms]], on="event_id", how="left")
    for metric, b in ((m, b) for ms in METRICS.values() for m in ms for b in ("beta_tlt", "beta_gld", "beta_iwm")):
        panel[f"ix_{metric}_{b}"] = panel[metric + "_z"] * panel[b]
    results = []
    feats = [f"ix_{m}_{b}" for ms in METRICS.values() for m in ms for b in ("beta_tlt", "beta_gld", "beta_iwm")]
    feats = [f for f in feats if f in panel.columns]
    for h in (1, 5, 10, 20):
        for feat in feats:
            ics, spreads = [], []
            for _, g in panel.groupby("event_id"):
                g = g.dropna(subset=[feat, f"fwd{h}"])
                if len(g) < 20: continue
                ic = stats.spearmanr(g[feat], g[f"fwd{h}"]).statistic
                if np.isfinite(ic): ics.append(ic)
                q = pd.qcut(g[feat].rank(method="first"), 5, labels=False)
                spreads.append(g[f"fwd{h}"][q == 4].mean() - g[f"fwd{h}"][q == 0].mean())
            if len(ics) < 10: continue
            t = stats.ttest_1samp(ics, 0); ts = stats.ttest_1samp(spreads, 0)
            results.append({"horizon": h, "feature": feat, "events": len(ics), "mean_ic": float(np.mean(ics)),
                            "ic_t": float(t.statistic), "ic_p": float(t.pvalue), "mean_spread": float(np.mean(spreads)),
                            "spread_t": float(ts.statistic), "spread_p": float(ts.pvalue)})
    res = pd.DataFrame(results)
    if not res.empty:
        res["ic_q"] = bh(res.ic_p); res["spread_q"] = bh(res.spread_p)
    res.to_csv(a.out / "p12_5_3_finsaber_event_results.csv", index=False)
    dates = sorted(panel.release_date.unique()); c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
    splits = {label: set(dates[lo:hi]) for label, lo, hi in (("train", 0, c1), ("validation", c1, c2), ("test", c2, len(dates)))}
    oos = []
    for fam, specs in PRIMARY.items():
        for metric, b in specs:
            feat = f"ix_{metric}_{b}"
            if feat not in panel.columns: continue
            for h in (1, 5, 10, 20):
                for label, ds in splits.items():
                    ics = []
                    for _, g in panel[(panel.event_type == fam) & panel.release_date.isin(ds)].groupby("event_id"):
                        g = g.dropna(subset=[feat, f"fwd{h}"])
                        if len(g) >= 20: ics.append(stats.spearmanr(g[feat], g[f"fwd{h}"]).statistic)
                    if ics: oos.append({"event_type": fam, "feature": feat, "horizon": h, "split": label, "events": len(ics), "mean_ic": float(np.mean(ics))})
    pd.DataFrame(oos).to_csv(a.out / "p12_5_3_finsaber_oos.csv", index=False)
    panel.to_csv(a.out / "p12_5_3_finsaber_panel.csv", index=False)
    summary = {"source": "FINSABER adjusted_close", "events_total": int(ev.event_id.nunique()), "events_used": int(panel.event_id.nunique()),
               "observations": int(len(panel)), "tickers": int(panel.ticker.nunique()),
               "event_types": panel.groupby("event_type").event_id.nunique().to_dict(),
               "date_range": [str(ev.release_date.min().date()), str(ev.release_date.max().date())],
               "best": res.sort_values("spread_p").head(6).to_dict("records") if len(res) else [],
               "oos": oos, "price_quality": "ADJUSTED_CLOSE_FINSABER_EXPLORATORY"}
    (a.out / "p12_5_3_finsaber_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
