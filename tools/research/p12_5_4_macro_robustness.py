#!/usr/bin/env python3
"""P12.5.4 macro-event robustness recomputation from local P12.5 panels."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

OUT = Path("data/research/p12_5_4"); OUT.mkdir(parents=True, exist_ok=True)
CPI = Path("../_us_research/data/research/macro_cross_sectional/p12_5_3_event_panel.csv")
FOMC = Path("../_us_research/data/research/macro_cross_sectional/fomc_rate_beta_panel.csv")
EVENTS = Path("../_us_research/data/research/macro_cross_sectional/bls_macro_events.csv")


def nw(x, lag):
    x = np.asarray(x, float); n = len(x)
    if n < 3: return np.nan, np.nan
    e = x - x.mean(); v = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    if v <= 0: return np.nan, np.nan
    t = x.mean() / np.sqrt(v / n)
    return float(t), float(2 * stats.norm.sf(abs(t)))


def block_boot(x, block, reps=2000, seed=20261123):
    x = np.asarray(x, float); n = len(x)
    if n < block: return (np.nan, np.nan)
    rng = np.random.default_rng(seed); nb = int(np.ceil(n / block)); out = np.empty(reps)
    for i in range(reps):
        starts = rng.integers(0, n - block + 1, nb)
        out[i] = np.concatenate([x[s:s + block] for s in starts]).mean()
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def bh(p):
    p = np.asarray(p, float); n = len(p); order = np.argsort(p); q = np.empty(n)
    prev = 1.0
    for rank in range(n - 1, -1, -1):
        i = order[rank]; prev = min(prev, p[i] * n / (rank + 1)); q[i] = prev
    return q


def holm(p):
    p = np.asarray(p, float); n = len(p); order = np.argsort(p); adj = np.empty(n); prev = 0.0
    for rank, i in enumerate(order):
        prev = max(prev, min(1.0, (n - rank) * p[i])); adj[i] = prev
    return adj


def run(df, features, family):
    rows = []
    df = df.copy(); df["event_date"] = pd.to_datetime(df["release_date"] if "release_date" in df else df["date"])
    for feat in features:
        for h in [1, 5, 10, 20]:
            y = f"fwd{h}"; g = df[[feat, y, "event_date", "event_id"]].dropna()
            if len(g) < 100: continue
            ics = []; spreads = []; evdates = []
            for d, gg in g.groupby("event_date"):
                if len(gg) < 30: continue
                ic = stats.spearmanr(gg[feat], gg[y]).statistic
                q = gg[feat].rank(pct=True)
                top = gg[y][q >= .8].mean(); bot = gg[y][q <= .2].mean()
                if np.isfinite(ic) and np.isfinite(top) and np.isfinite(bot):
                    ics.append(ic); spreads.append(top - bot); evdates.append(d)
            if len(ics) < 10: continue
            ev = pd.DataFrame({"date": evdates, "ic": ics, "spread": spreads}).sort_values("date")
            t4, p4 = nw(ev.ic, 4); ts, ps = nw(ev.spread, 4)
            lo, hi = block_boot(ev.spread, 5)
            n = len(ev); tr = int(n * .6); va = int(n * .8)
            rows.append({"family": family, "feature": feat, "horizon": h, "events": n,
                         "mean_ic": ev.ic.mean(), "hac_t_ic": t4, "p_ic": p4,
                         "mean_spread": ev.spread.mean(), "hac_t_spread": ts, "p_spread": ps,
                         "boot_low": lo, "boot_high": hi,
                         "train_ic": ev.ic.iloc[:tr].mean(), "val_ic": ev.ic.iloc[tr:va].mean(), "test_ic": ev.ic.iloc[va:].mean(),
                         "train_spread": ev.spread.iloc[:tr].mean(), "val_spread": ev.spread.iloc[tr:va].mean(), "test_spread": ev.spread.iloc[va:].mean()})
    return pd.DataFrame(rows)


panel = pd.read_csv(CPI)
cpi_feats = [c for c in panel.columns if c.startswith("ix_")]
emp = panel[panel.event_type == "employment"]; cp = panel[panel.event_type == "cpi"]
res = pd.concat([run(cp, cpi_feats, "CPI"), run(emp, [c for c in cpi_feats if "payroll" in c or "unemployment" in c or "earnings" in c], "EMPLOYMENT")], ignore_index=True)
# family-wide BH and global Holm
res["q_bh_family"] = np.nan
for fam in res.family.unique():
    idx = res.family == fam; res.loc[idx, "q_bh_family"] = bh(res.loc[idx, "p_spread"])
res["q_bh_global"] = bh(res.p_spread); res["p_holm"] = holm(res.p_spread)
res.to_csv(OUT / "m3_event_results.csv", index=False)
# HAC sensitivity for top 10 by |spread|
hac_rows = []
for _, r in res.reindex(res.mean_spread.abs().sort_values(ascending=False).index).head(10).iterrows():
    d = panel if r.family == "CPI" else emp
    g = d[[r.feature, f"fwd{int(r.horizon)}", "release_date"]].dropna()
    ser = []
    for date, gg in g.groupby("release_date"):
        if len(gg) < 30: continue
        q = gg[r.feature].rank(pct=True); ser.append(gg[f"fwd{int(r.horizon)}"][q >= .8].mean() - gg[f"fwd{int(r.horizon)}"][q <= .2].mean())
    for lag in [0, 1, 2, 3, 4, 5, 8, 10]:
        t, p = nw(ser, lag); hac_rows.append({"family": r.family, "feature": r.feature, "horizon": r.horizon, "lag": lag, "t": t, "p": p})
pd.DataFrame(hac_rows).to_csv(OUT / "m3_hac_sensitivity.csv", index=False)
# Bootstrap core 3 assumptions, 2000 (resource-bound; documented).
boot = []
for feat in ["ix_initial_payroll_change_beta_iwm", "ix_initial_headline_value_beta_tlt", "ix_initial_core_value_beta_tlt"]:
    r = res[(res.feature == feat) & (res.horizon == 20)].iloc[0]
    d = panel if r.family == "CPI" else emp
    g = d[[feat, "fwd20", "release_date"]].dropna(); ser = []
    for date, gg in g.groupby("release_date"):
        if len(gg) < 30: continue
        q = gg[feat].rank(pct=True); ser.append(gg.fwd20[q >= .8].mean() - gg.fwd20[q <= .2].mean())
    for b in [3, 5, 8]:
        lo, hi = block_boot(ser, b, 2000); boot.append({"feature": feat, "horizon": 20, "block": b, "reps": 2000, "low": lo, "high": hi})
pd.DataFrame(boot).to_csv(OUT / "m3_block_bootstrap.csv", index=False)
# FOMC
f = pd.read_csv(FOMC)
f["date"] = pd.to_datetime(f.date)
fres = run(f, ["beta_spy_z", "beta_tlt_z", "vol20_z", "mom20_z"], "FOMC")
fres["q_bh_family"] = bh(fres.p_spread); fres["q_bh_global"] = bh(fres.p_spread); fres["p_holm"] = holm(fres.p_spread)
fres.to_csv(OUT / "m3_fomc_results.csv", index=False)
# combine multiple testing
allr = pd.concat([res.assign(family=res.family), fres.assign(family="FOMC")], ignore_index=True)
allr["q_bh_all"] = bh(allr.p_spread); allr["p_holm_all"] = holm(allr.p_spread)
allr.to_csv(OUT / "m3_multiple_testing.csv", index=False)
summary = {"cpi_events": int(cp.event_id.nunique()), "employment_events": int(emp.event_id.nunique()),
           "cpi_rows": len(cp), "employment_rows": len(emp), "fomc_events": int(f.event_id.nunique()),
           "tests": len(allr), "top": allr.sort_values("p_spread").head(5)[["family", "feature", "horizon", "events", "mean_spread", "p_spread", "q_bh_all", "p_holm_all", "test_spread"]].to_dict("records"),
           "min_q": float(allr.q_bh_all.min()), "status": "NO_GO"}
(OUT / "p12_5_4_final_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p12_5_4_output_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2, default=str))
