#!/usr/bin/env python3
"""P12.5.3 exploratory CPI/Employment cross-sectional pilot.

Uses the existing unadjusted PIT price snapshot and ALFRED date-only events.
This is explicitly exploratory: no total-return or PIT-membership claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

METRICS = {
    "cpi": ["initial_headline_value", "initial_core_value", "headline_yoy", "core_yoy"],
    "employment": ["initial_payroll_change", "initial_unemployment_rate", "initial_earnings_mom", "initial_earnings_yoy"],
}
PRIMARY = {
    "cpi": [("initial_headline_value", "beta_tlt"), ("initial_core_value", "beta_tlt"), ("initial_headline_value", "beta_gld")],
    "employment": [("initial_payroll_change", "beta_iwm"), ("initial_unemployment_rate", "beta_iwm"), ("initial_earnings_mom", "beta_tlt")],
}


def load_prices(path):
    df = pd.read_csv(path, usecols=["Technical_Date", "Ticker", "Price"])
    df["date"] = pd.to_datetime(df.Technical_Date)
    return df.dropna().drop_duplicates(["date", "Ticker"]).pivot(index="date", columns="Ticker", values="Price").sort_index()


def load_etf(path):
    df = pd.read_csv(path, usecols=["Date", "Adj Close"])
    df["date"] = pd.to_datetime(df.Date, utc=True).dt.tz_convert(None).dt.normalize()
    return df.set_index("date")["Adj Close"].sort_index()


def beta(s, spy, tlt, gld, iwm, end, window=252, min_obs=180):
    r = pd.concat([s.pct_change(), spy.pct_change(), tlt.pct_change(), gld.pct_change(), iwm.pct_change()], axis=1, join="inner").dropna()
    r = r[r.index <= end].tail(window)
    if len(r) < min_obs:
        return None
    X = np.column_stack([np.ones(len(r)), r.iloc[:, 1], r.iloc[:, 2], r.iloc[:, 3], r.iloc[:, 4]])
    coef, *_ = np.linalg.lstsq(X, r.iloc[:, 0].to_numpy(), rcond=None)
    return {"beta_spy": float(coef[1]), "beta_tlt": float(coef[2]), "beta_gld": float(coef[3]), "beta_iwm": float(coef[4])}


def fwd(s, spy, t0, h):
    idx = s.index[s.index >= t0]
    sidx = spy.index[spy.index >= t0]
    if len(idx) < h + 1 or len(sidx) < h + 1:
        return None
    return s[idx[h]] / s[idx[0]] - 1 - (spy[sidx[h]] / spy[sidx[0]] - 1)


def z_dev(series):
    hist = series.shift(1)
    med = hist.rolling(36, min_periods=36).median()
    mad = hist.rolling(36, min_periods=36).apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)
    z = (series - med) / (1.4826 * mad)
    return z.replace([np.inf, -np.inf], np.nan)


def bh(p):
    p = np.asarray(p, float); n = len(p); order = np.argsort(p); q = np.empty(n); prev = 1.0
    for rank in range(n - 1, -1, -1):
        i = order[rank]; prev = min(prev, p[i] * n / (rank + 1)); q[i] = prev
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--spy", type=Path, required=True); ap.add_argument("--tlt", type=Path, required=True)
    ap.add_argument("--gld", type=Path, required=True); ap.add_argument("--iwm", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    prices = load_prices(a.snapshot)
    etfs = {k: load_etf(p) for k, p in {"spy": a.spy, "tlt": a.tlt, "gld": a.gld, "iwm": a.iwm}.items()}
    spy = etfs["spy"]; sessions = spy.index
    for k in etfs:
        etfs[k] = etfs[k].reindex(sessions).ffill()
    ev_all = pd.read_csv(a.events)
    ev_all["release_date"] = pd.to_datetime(ev_all.release_date)
    ev = ev_all[ev_all.release_date >= "2017-01-01"].copy()
    # Signal is prior close; entry is next complete session after release.
    rows = []
    for _, e in ev.iterrows():
        pre = prices.index[prices.index < e.release_date]
        post = sessions[sessions > e.release_date]
        if len(pre) < 252 or len(post) < 21:
            continue
        signal = pre[-1]; entry = post[0]
        for ticker in prices.columns:
            s = prices[ticker].dropna()
            b = beta(s, etfs["spy"], etfs["tlt"], etfs["gld"], etfs["iwm"], signal)
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
    # Macro deviations are per event/family and use prior 36 events only.
    evz = ev_all.copy()
    for fam, metrics in METRICS.items():
        g = evz[evz.event_type == fam].sort_values("release_date").copy()
        for m in metrics:
            g[m + "_z"] = z_dev(pd.to_numeric(g[m], errors="coerce"))
        evz.loc[g.index, [m + "_z" for m in metrics]] = g[[m + "_z" for m in metrics]]
    panel = panel.merge(evz[["event_id"] + [m + "_z" for ms in METRICS.values() for m in ms]], on="event_id", how="left")
    for key, b in (("initial_headline_value", "beta_tlt"), ("initial_core_value", "beta_tlt"), ("initial_headline_value", "beta_gld"),
                   ("initial_payroll_change", "beta_iwm"), ("initial_unemployment_rate", "beta_iwm"), ("initial_earnings_mom", "beta_tlt"),
                   ("initial_earnings_yoy", "beta_tlt"), ("headline_yoy", "beta_tlt"), ("core_yoy", "beta_tlt")):
        panel[f"ix_{key}_{b}"] = panel[key + "_z"] * panel[b]
    results = []
    feats = sorted({c for ms in METRICS.values() for m in ms for c in [f"ix_{m}_beta_tlt", f"ix_{m}_beta_gld", f"ix_{m}_beta_iwm"]} & set(panel.columns))
    for h in (1, 5, 10, 20):
        for feat in feats:
            ics, spreads, ns = [], [], []
            for eid, g in panel.groupby("event_id"):
                g = g.dropna(subset=[feat, f"fwd{h}"])
                if len(g) < 20: continue
                ic = stats.spearmanr(g[feat], g[f"fwd{h}"]).statistic
                if np.isfinite(ic): ics.append(ic)
                q = pd.qcut(g[feat].rank(method="first"), 5, labels=False)
                spreads.append(g[f"fwd{h}"][q == 4].mean() - g[f"fwd{h}"][q == 0].mean())
                ns.append(len(g))
            if len(ics) < 10: continue
            t = stats.ttest_1samp(ics, 0); ts = stats.ttest_1samp(spreads, 0)
            results.append({"horizon": h, "feature": feat, "events": len(ics), "mean_n": float(np.mean(ns)),
                            "mean_ic": float(np.mean(ics)), "ic_t": float(t.statistic), "ic_p": float(t.pvalue),
                            "mean_spread": float(np.mean(spreads)), "spread_t": float(ts.statistic), "spread_p": float(ts.pvalue)})
    res = pd.DataFrame(results)
    if not res.empty:
        res["ic_q"] = bh(res.ic_p); res["spread_q"] = bh(res.spread_p)
    # OOS: primary interaction per family/horizon, 60/20/20 by event date.
    dates = sorted(panel.release_date.unique()); c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
    split_dates = {"train": set(dates[:c1]), "validation": set(dates[c1:c2]), "test": set(dates[c2:])}
    splits = {k: set(panel[panel.release_date.isin(v)].event_id) for k, v in split_dates.items()}
    oos = []
    for fam, specs in PRIMARY.items():
        for metric, b in specs:
            feat = f"ix_{metric}_{b}"
            if feat not in panel.columns: continue
            for h in (1, 5, 10, 20):
                for label, ids in splits.items():
                    ics = []
                    for eid in ids:
                        g = panel[(panel.event_id == eid) & panel.event_type.eq(fam)].dropna(subset=[feat, f"fwd{h}"])
                        if len(g) >= 20: ics.append(stats.spearmanr(g[feat], g[f"fwd{h}"]).statistic)
                    if ics:
                        oos.append({"event_type": fam, "feature": feat, "horizon": h, "split": label,
                                    "events": len(ics), "mean_ic": float(np.mean(ics))})
    pd.DataFrame(oos).to_csv(a.out / "p12_5_3_oos_results.csv", index=False)
    res.to_csv(a.out / "p12_5_3_event_results.csv", index=False)
    pd.DataFrame(columns=["feature", "horizon", "coefficient", "note"]).to_csv(a.out / "p12_5_3_factor_results.csv", index=False)
    panel.to_csv(a.out / "p12_5_3_event_panel.csv", index=False)
    summary = {"events_total": int(ev.event_id.nunique()), "events_used": int(panel.event_id.nunique()),
               "event_types": panel.groupby("event_type").event_id.nunique().to_dict(),
               "observations": int(len(panel)), "tickers": int(panel.ticker.nunique()),
               "mean_names_per_event": panel.groupby("event_id").size().describe().to_dict(),
               "best_tests": res.sort_values("spread_p").head(8).to_dict("records") if len(res) else [],
               "oos": oos, "price_quality": "UNADJUSTED_CLOSE_ONLY_EXPLORATORY",
               "timestamp_quality": "DATE_ONLY_ALFRED_VINTAGE"}
    (a.out / "p12_5_3_event_panel_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
