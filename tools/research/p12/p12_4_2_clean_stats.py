"""P12.4.2 2.02/5.02 clean-sample and overlap statistics."""
import numpy as np
import pandas as pd

from tools.research.p12.p12_4_2_stats import bh, boot_mean

ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]
OUT = ROOT / "data/research/p12_4_2"


def main():
    e = pd.read_csv(OUT / "p12_4_2_8k_panel.csv")
    e["period"] = np.where(e.filing_date <= "2018-12-31", "explore", "validate")
    rows = []
    for item, sess in (("5.02", "AFTER_HOURS"), ("2.02", "AFTER_HOURS"), ("7.01", "PREMARKET"), ("8.01", "PREMARKET")):
        base = e[(e.event_session == sess) & e["items"].astype(str).str.contains(rf"(?<![\d.]){item.replace('.', r'\.')}(?![\d.])", regex=True)]
        for period in ("all", "explore", "validate"):
            p = base if period == "all" else base[base.period == period]
            for sample, z in (("all", p), ("no_overlap", p[p.overlap_20d == 0]), ("no_same_day", p[p.same_day_filing == 0]), ("clean_both", p[(p.overlap_20d == 0) & (p.same_day_filing == 0)])):
                for h in (5, 20):
                    col = f"ex{h}_return"
                    x = z[[col, "cik"]].dropna()
                    if len(x) < 2:
                        continue
                    m, lo, hi, pv = boot_mean(x[col], x.cik, 500)
                    rows.append({"item": item, "session": sess, "period": period, "sample": sample, "horizon": h, "n": len(x), "issuers": x.cik.nunique(), "mean": m, "median": x[col].median(), "positive": (x[col] > 0).mean(), "ci_low": lo, "ci_high": hi, "p": pv})
    d = pd.DataFrame(rows)
    for h in (5, 20):
        m = d.horizon == h
        d.loc[m, "bh_q"] = bh(d.loc[m, "p"].tolist())
    d.to_csv(OUT / "p12_4_2_clean_window_stats.csv", index=False)


if __name__ == "__main__":
    main()
