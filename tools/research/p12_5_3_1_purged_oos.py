import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

out = Path("data/research/macro_cross_sectional")
p = pd.read_csv(out / "p12_5_3_event_panel.csv", parse_dates=["release_date"])
purge = json.loads((out / "p12_5_3_1_purge.json").read_text())
dates = sorted(p.release_date.dt.normalize().unique())
c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
splits = {"train": set(dates[:c1]) - set(pd.to_datetime(purge["removed_train"])),
          "validation": set(dates[c1:c2]) - set(pd.to_datetime(purge["removed_validation"])),
          "test": set(dates[c2:])}
specs = {"cpi": [("ix_initial_headline_value_beta_tlt"), ("ix_initial_core_value_beta_tlt"), ("ix_initial_headline_value_beta_gld")],
         "employment": [("ix_initial_payroll_change_beta_iwm"), ("ix_initial_unemployment_rate_beta_iwm"), ("ix_initial_earnings_mom_beta_tlt")]}
rows = []
for fam, feats in specs.items():
    for f in feats:
        for h in (1, 5, 10, 20):
            for label, ds in splits.items():
                ics = []
                for _, g in p[(p.event_type == fam) & p.release_date.dt.normalize().isin(ds)].groupby("event_id"):
                    g = g.dropna(subset=[f, f"fwd{h}"])
                    if len(g) >= 20:
                        ics.append(stats.spearmanr(g[f], g[f"fwd{h}"]).statistic)
                if ics:
                    rows.append({"event_type": fam, "feature": f, "horizon": h, "split": label,
                                 "events": len(ics), "mean_ic": float(np.mean(ics))})
pd.DataFrame(rows).to_csv(out / "p12_5_3_1_oos_purged.csv", index=False)
print(pd.DataFrame(rows).query("horizon == 20").to_string(index=False))
