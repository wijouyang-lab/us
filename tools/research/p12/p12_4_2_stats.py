"""P12.4.1 market-excess, cluster bootstrap, and BH-FDR summaries."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/research/p12_4_2"
SPY = ROOT.parent / "pr512/data/research/p9_1_support_resistance/spy.csv"


def bh(p):
    p = np.asarray(p, dtype=float)
    out = np.full(len(p), np.nan)
    ok = np.isfinite(p)
    idx = np.where(ok)[0]
    if len(idx) == 0:
        return out
    order = idx[np.argsort(p[idx])]
    prev = 1.0
    for rank in range(len(order), 0, -1):
        i = order[rank - 1]
        prev = min(prev, p[i] * len(order) / rank)
        out[i] = prev
    return out


def boot_mean(x, cik, reps=500):
    x = np.asarray(x, dtype=float); cik = np.asarray(cik)
    ok = np.isfinite(x)
    x, cik = x[ok], cik[ok]
    if len(x) < 5:
        return np.nan, np.nan, np.nan, np.nan
    rng = np.random.default_rng(20261117)
    groups = {c: x[cik == c] for c in np.unique(cik)}
    keys = list(groups)
    means = []
    for _ in range(reps):
        pick = rng.choice(keys, size=len(keys), replace=True)
        vals = np.concatenate([groups[c] for c in pick])
        means.append(vals.mean())
    means = np.array(means)
    # Finite-sample corrected two-sided bootstrap p; never exactly zero.
    p = min(1.0, 2 * min(((means <= 0).sum() + 1) / (reps + 1), ((means >= 0).sum() + 1) / (reps + 1)))
    return x.mean(), np.quantile(means, .025), np.quantile(means, .975), p


def main():
    spy = pd.read_csv(SPY, parse_dates=["Date"]).set_index("Date").close.sort_index()
    spy.index = spy.index.date
    e = pd.read_csv(OUT / "p12_4_2_8k_panel.csv")
    for h in (5, 20):
        e[f"ex{h}_return"] = np.nan
    for i, r in e.iterrows():
        base = r["reaction_date"]
        if not isinstance(base, str):
            continue
        base_date = pd.Timestamp(base).date()
        if base_date not in spy.index:
            continue
        k = list(spy.index).index(base_date)
        for h in (5, 20):
            if k + h < len(spy.index):
                ex = spy.index[k + h]
                e.at[i, f"ex{h}_return"] = float(r[f"d{h}_return"] - (spy.loc[ex] / spy.loc[base_date] - 1)) if pd.notna(r[f"d{h}_return"]) else np.nan
    e.to_csv(OUT / "p12_4_2_8k_panel.csv", index=False)
    e["period"] = np.where(e.filing_date <= "2018-12-31", "explore", np.where(e.filing_date >= "2019-01-01", "validate", "other"))
    rows = []
    for item in ("1.01", "2.01", "2.02", "2.03", "5.02", "5.07", "7.01", "8.01"):
        for sess in ("PREMARKET", "INTRADAY", "AFTER_HOURS", "NON_TRADING"):
            for period in ("all", "explore", "validate"):
                x = e[e["items"].str.contains(rf"(?<![\d.]){item}(?![\d.])", regex=True) & (e.event_session == sess)]
                if period != "all":
                    x = x[x.period == period]
                x = x.dropna(subset=["d5_return"])
                if len(x) < 1:
                    continue
                m, lo, hi, p = boot_mean(x.ex5_return, x.cik)
                m20, lo20, hi20, p20 = boot_mean(x.ex20_return, x.cik)
                rows.append({"item": item, "session": sess, "period": period, "n_accessions": len(x), "n_issuers": x.cik.nunique(),
                             "d5_raw_mean": x.d5_return.mean(), "d5_excess_mean": m, "d5_ci_low": lo, "d5_ci_high": hi, "d5_p": p,
                             "d20_excess_mean": m20, "d20_ci_low": lo20, "d20_ci_high": hi20, "d20_p": p20,
                             "d5_positive": (x.d5_return > 0).mean(), "same_day_filing_rate": x.same_day_filing.mean(), "overlap_rate": x.overlap_20d.mean()})
    s = pd.DataFrame(rows)
    s["d5_bh_q"] = bh(s.d5_p.tolist())
    s["d20_bh_q"] = bh(s.d20_p.tolist())
    s["inference"] = np.where((s.n_accessions >= 100) & (s.n_issuers >= 20), "ELIGIBLE", "DESCRIPTIVE_ONLY")
    s.to_csv(OUT / "p12_4_2_8k_stats.csv", index=False)

    f = pd.read_csv(OUT / "p12_4_2_fundamental_panel.csv")
    f["known_at"] = pd.to_datetime(f.known_at, utc=True)
    rows = []
    for m in ("revenue_growth", "op_margin_change", "cash_conversion", "leverage_change", "shares_change"):
        for h in (5, 10, 20):
            for period, a, b in (("all", "2009-01-01", "2024-12-31"), ("explore", "2009-01-01", "2018-12-31"), ("validate", "2019-01-01", "2024-12-31")):
                x = f[(f.known_at >= a) & (f.known_at <= b)][["cik", m, f"ret{h}", f"ex{h}"]].dropna(subset=[m, f"ret{h}"])
                if len(x) < 10:
                    continue
                ic = x[m].corr(x[f"ret{h}"], method="spearman") if x[m].nunique() > 1 else np.nan
                rng = np.random.default_rng(20261117); keys = list(x.cik.unique()); ics = []
                for _ in range(500):
                    pick = rng.choice(keys, size=len(keys), replace=True)
                    z = pd.concat([x[x.cik == c] for c in pick])
                    ics.append(z[m].corr(z[f"ret{h}"], method="spearman"))
                ics = pd.Series(ics).dropna()
                p_ic = min(1.0, 2 * min(((ics <= 0).sum() + 1) / (len(ics) + 1), ((ics >= 0).sum() + 1) / (len(ics) + 1))) if len(ics) else np.nan
                rows.append({"metric": m, "horizon": h, "period": period, "n_events": len(x), "n_issuers": x.cik.nunique(),
                             "rank_ic": ic, "ic_p": p_ic, "ic_ci_low": ics.quantile(.025) if len(ics) else np.nan, "ic_ci_high": ics.quantile(.975) if len(ics) else np.nan,
                             "mean_ret": x[f"ret{h}"].mean(), "mean_excess": x[f"ex{h}"].mean(),
                             "median_ret": x[f"ret{h}"].median(), "positive_rate": (x[f"ret{h}"] > 0).mean(),
                             "top_tercile_excess": x[x[m].rank(pct=True) > 2/3][f"ex{h}"].mean(), "bottom_tercile_excess": x[x[m].rank(pct=True) <= 1/3][f"ex{h}"].mean(),
                             "n_eligible": (len(x) >= 100 and x.cik.nunique() >= 20)})
    fs = pd.DataFrame(rows)
    fs["ic_bh_q"] = bh(fs.ic_p.tolist())
    fs["inference"] = np.where(fs.n_eligible, "ELIGIBLE", "DESCRIPTIVE_ONLY")
    fs.to_csv(OUT / "p12_4_2_fundamental_stats.csv", index=False)
    print({"8k_rows": len(s), "fund_rows": len(fs), "fund_accessions": int(f.accession.nunique())})


if __name__ == "__main__":
    main()
