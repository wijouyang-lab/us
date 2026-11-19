#!/usr/bin/env python3
"""P12.5.3.1 HAC/bootstrap and purge for the exploratory event panel."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

OUT = Path("data/research/macro_cross_sectional")
panel = pd.read_csv(OUT / "p12_5_3_event_panel.csv", parse_dates=["release_date", "entry"])
res = pd.read_csv(OUT / "p12_5_3_event_results.csv")
panel["date"] = panel.release_date.dt.normalize()


def nw(x, lag):
    x = np.asarray(x, float); n = len(x); e = x - x.mean()
    var = np.dot(e, e) / n
    for k in range(1, min(lag, n - 1) + 1):
        var += 2 * (1 - k / (lag + 1)) * np.dot(e[k:], e[:-k]) / n
    return x.mean() / np.sqrt(var / n) if var > 0 else np.nan


def ic_spread(feat, h):
    rows = []
    for (eid, d), g in panel.groupby(["event_id", "date"]):
        g = g.dropna(subset=[feat, f"fwd{h}"])
        if len(g) < 20: continue
        rows.append((d, eid, stats.spearmanr(g[feat], g[f"fwd{h}"]).statistic,
                     g[f"fwd{h}"][pd.qcut(g[feat].rank(method="first"), 5, labels=False) == 4].mean()
                     - g[f"fwd{h}"][pd.qcut(g[feat].rank(method="first"), 5, labels=False) == 0].mean()))
    return pd.DataFrame(rows, columns=["date", "event_id", "ic", "spread"])


hac = []
boot_rows = []
rng = np.random.default_rng(20261119)
cache = {}
for _, r in res.iterrows():
    key = (r.feature, int(r.horizon))
    if key not in cache:
        cache[key] = ic_spread(*key)
    s = cache[key]
    if len(s) < 10:
        continue
    for lag in range(5):
        hac.append({"feature": r.feature, "horizon": int(r.horizon), "events": len(s), "lag": lag,
                    "mean_ic": s.ic.mean(), "nw_ic_t": nw(s.ic, lag),
                    "mean_spread": s.spread.mean(), "nw_spread_t": nw(s.spread, lag)})
    # same-date block aggregates, 5,000 resamples, fixed seed
    blocks = s.groupby("date").spread.mean().to_numpy()
    means = rng.choice(blocks, size=(5000, len(blocks)), replace=True).mean(axis=1)
    boot_rows.append({"feature": r.feature, "horizon": int(r.horizon), "events": len(s),
                      "blocks": len(blocks), "boot_mean": float(np.mean(means)),
                      "boot_ci_low": float(np.quantile(means, .025)),
                      "boot_ci_high": float(np.quantile(means, .975))})
pd.DataFrame(hac).to_csv(OUT / "p12_5_3_1_hac_sensitivity.csv", index=False)
pd.DataFrame(boot_rows).to_csv(OUT / "p12_5_3_1_bootstrap.csv", index=False)

# Purge: drop train/validation events whose D20 window reaches the next split.
spy = pd.read_csv("data/research/volume_shock_reversal/SPY.csv", usecols=["Date"])
spy["date"] = pd.to_datetime(spy.Date, utc=True).dt.tz_convert(None).dt.normalize()
sessions = pd.DatetimeIndex(sorted(set(spy.date)))
dates = sorted(panel.date.unique()); c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
train_dates, val_dates, test_dates = set(dates[:c1]), set(dates[c1:c2]), set(dates[c2:])
val_start, test_start = dates[c1], dates[c2]


def crosses(d, boundary):
    pos = sessions.get_loc(d) if d in sessions else None
    if pos is None or pos + 20 >= len(sessions): return True
    return sessions[pos + 20] >= boundary


train_keep = {d for d in train_dates if not crosses(d, val_start)}
val_keep = {d for d in val_dates if not crosses(d, test_start)}
purge = {"raw_train": len(train_dates), "raw_validation": len(val_dates), "raw_test": len(test_dates),
         "purged_train": len(train_keep), "purged_validation": len(val_keep), "purged_test": len(test_dates),
         "removed_train": sorted(str(x.date()) for x in train_dates - train_keep),
         "removed_validation": sorted(str(x.date()) for x in val_dates - val_keep)}
(OUT / "p12_5_3_1_purge.json").write_text(json.dumps(purge, indent=2), encoding="utf-8")
print(json.dumps(purge, indent=2))
print(pd.DataFrame(hac).query("lag == 4").sort_values("nw_spread_t").head(5).to_string(index=False))
