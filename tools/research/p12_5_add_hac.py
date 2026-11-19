import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

out = Path("data/research/macro_cross_sectional")
panel = pd.read_csv(out / "fomc_rate_beta_panel.csv")
rows = []
for h in (1, 5, 10, 20):
    spreads, ics = [], []
    for eid, g in panel.groupby("event_id"):
        g = g.dropna(subset=["beta_tlt", f"fwd{h}"])
        if len(g) < 20:
            continue
        q = pd.qcut(g.beta_tlt.rank(method="first"), 5, labels=False)
        spreads.append(g[f"fwd{h}"][q == 4].mean() - g[f"fwd{h}"][q == 0].mean())
        ics.append(stats.spearmanr(g.beta_tlt, g[f"fwd{h}"]).statistic)
    x = np.asarray(spreads, float)
    n = len(x)
    e = x - x.mean()
    var = np.dot(e, e) / n
    for k in range(1, 4):
        var += 2 * (1 - k / 4) * np.dot(e[k:], e[:-k]) / n
    nw = x.mean() / np.sqrt(var / n)
    rng = np.random.default_rng(7)
    means = rng.choice(x, size=(5000, n), replace=True).mean(axis=1)
    rows.append({"horizon": h, "events": n, "mean_spread": x.mean(),
                 "nw_t": nw, "nw_p": 2 * stats.t.sf(abs(nw), n - 1),
                 "boot_ci_low": float(np.quantile(means, .025)),
                 "boot_ci_high": float(np.quantile(means, .975)),
                 "mean_ic": float(np.mean(ics))})
res = pd.DataFrame(rows)
res.to_csv(out / "event_results_hac.csv", index=False)
print(res.to_string(index=False))
