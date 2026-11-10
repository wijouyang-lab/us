#!/usr/bin/env python3
"""Daily cross-sectional IC / Rank IC and quintile validation for Phase 2.5.

Label: EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED.
Not PIT; IC is not strategy alpha.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from tools.research.factor_engine import FACTORS
HORIZONS = (1, 5, 10, 20, 60)
MIN_NAMES = 30
START = "2018-01-01"


def newey_west_pvalue(x, max_lag=None):
    x = np.asarray(x, float)
    n = len(x)
    if n < 3:
        return None, None, None
    mu = x.mean()
    e = x - mu
    lag = max_lag if max_lag is not None else int(np.floor(4 * (n / 100) ** (2 / 9)))
    gamma0 = np.dot(e, e) / n
    var = gamma0
    for l in range(1, lag + 1):
        if l >= n:
            break
        gamma = np.dot(e[l:], e[:-l]) / n
        var += 2 * (1 - l / (lag + 1)) * gamma
    se = np.sqrt(max(var, 0) / n)
    if se == 0:
        return mu, se, None
    z = mu / se
    return mu, se, 2 * (1 - norm.cdf(abs(z)))


def bh_fdr(pvals):
    p = np.asarray(pvals, float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    idx = np.where(ok)[0]
    order = idx[np.argsort(p[idx])]
    m = len(order)
    prev = 1.0
    for rank, i in enumerate(order[::-1], start=1):
        val = min(prev, p[i] * m / (m - rank + 1))
        q[i] = val
        prev = val
    return q


def load_factors(path):
    d = pd.read_parquet(path)
    d["Date"] = pd.to_datetime(d["Date"])
    return d


def validate(factor_path, label_dir, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    f = load_factors(factor_path)
    f = f[f.Date >= pd.Timestamp(START)]
    details = []
    summaries = []
    annual = []
    for h in HORIZONS:
        lab = pd.read_parquet(Path(label_dir) / f"labels_{h}d.parquet",
                              columns=["Ticker", "Signal_Date", "Forward_Return", "Sample_Status"])
        lab = lab[lab.Sample_Status == "MATURED"].copy()
        lab["Signal_Date"] = pd.to_datetime(lab["Signal_Date"])
        m = f.merge(lab, left_on=["Ticker", "Date"], right_on=["Ticker", "Signal_Date"], how="inner")
        for factor in FACTORS:
            sub = m[["Date", "Ticker", factor, "Forward_Return"]].dropna()
            for dt, g in sub.groupby("Date", sort=True):
                if len(g) < MIN_NAMES or g[factor].nunique() < 3:
                    continue
                ic = g[factor].corr(g["Forward_Return"])
                ric = g[factor].corr(g["Forward_Return"], method="spearman")
                q = pd.qcut(g[factor].rank(method="first"), 5, labels=False, duplicates="drop")
                qmeans = g.groupby(q)["Forward_Return"].mean()
                if len(qmeans) < 5:
                    continue
                details.append({"Date": dt.date().isoformat(), "Horizon": h, "Factor": factor,
                                "IC": ic, "RankIC": ric, "N": len(g),
                                "Q1": qmeans.get(0), "Q2": qmeans.get(1), "Q3": qmeans.get(2),
                                "Q4": qmeans.get(3), "Q5": qmeans.get(4),
                                "Q5_Q1": qmeans.get(4) - qmeans.get(0)})
    det = pd.DataFrame(details)
    det.to_parquet(out / "daily_ic.parquet", index=False)
    for (h, factor), g in det.groupby(["Horizon", "Factor"]):
        ic = g["IC"].dropna().to_numpy()
        ric = g["RankIC"].dropna().to_numpy()
        mu, se, p = newey_west_pvalue(ic)
        _, _, pr = newey_west_pvalue(ric)
        summaries.append({"Horizon": h, "Factor": factor, "ValidDates": len(g),
                          "MeanIC": ic.mean(), "MeanRankIC": ric.mean(),
                          "ICStd": ic.std(ddof=1), "RankICStd": ric.std(ddof=1),
                          "ICIR": ic.mean() / ic.std(ddof=1) if ic.std(ddof=1) else None,
                          "RankICIR": ric.mean() / ric.std(ddof=1) if ric.std(ddof=1) else None,
                          "PositiveIC": float((ic > 0).mean()), "PositiveRankIC": float((ric > 0).mean()),
                          "MedianN": float(g["N"].median()), "MinN": int(g["N"].min()), "MaxN": int(g["N"].max()),
                          "NW_p_IC": p, "NW_p_RankIC": pr,
                          "MeanQ5_Q1": float(g["Q5_Q1"].mean()),
                          "PositiveQ5_Q1": float((g["Q5_Q1"] > 0).mean())})
        for year, yg in g.groupby(pd.to_datetime(g["Date"]).dt.year):
            annual.append({"Year": int(year), "Horizon": h, "Factor": factor,
                           "MeanIC": yg["IC"].mean(), "MeanRankIC": yg["RankIC"].mean(),
                           "ValidDates": len(yg), "MedianN": float(yg["N"].median())})
    s = pd.DataFrame(summaries)
    s["q_IC"] = bh_fdr(s["NW_p_IC"].to_numpy())
    s["q_RankIC"] = bh_fdr(s["NW_p_RankIC"].to_numpy())
    s.to_csv(out / "summary.csv", index=False)
    pd.DataFrame(annual).to_csv(out / "annual.csv", index=False)
    (out / "summary.json").write_text(json.dumps({"label": "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED",
                                                 "start": START, "rows": len(det),
                                                 "summary": s.to_dict(orient="records")}, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(det), "summaries": len(s)}, indent=2))
    return s


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--factors", required=True)
    p.add_argument("--labels", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    validate(a.factors, a.labels, a.output)
