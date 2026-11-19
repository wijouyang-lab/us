#!/usr/bin/env python3
"""P13.1.1 corrected coverage, calendar alignment, HAC(19), purge and bootstrap."""
from __future__ import annotations

import bisect
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

OUT = Path("data/research/p13_1")
OUT.mkdir(parents=True, exist_ok=True)
PRICES = Path("../_us_audit/pr512/data/research/pit_data/finsaber_prices_raw.csv")
MEMBERS = Path("../_us_audit/pr512/data/research/historical_universe/sp500_daily.csv")
SPY = Path("../_us_audit/pr512/data/research/p9_1_support_resistance/SPY.csv")
START5, END = pd.Timestamp("2020-01-02"), pd.Timestamp("2024-12-31")
START3 = pd.Timestamp("2022-01-03")


def nw(x, lag):
    x = np.asarray(x, float); n = len(x); e = x - x.mean(); v = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(v / n) if v > 0 else np.nan


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); q = np.empty(n); prev = 1.0
    for rank in range(n - 1, -1, -1):
        i = o[rank]; prev = min(prev, p[i] * n / (rank + 1)); q[i] = prev
    return q


# Calendar from SPY, exact and unique.
spy_raw = pd.read_csv(SPY, usecols=["Date", "close"])
spy_raw["date"] = pd.to_datetime(spy_raw.Date, utc=True).dt.tz_convert(None).dt.normalize()
dup_spy = int(spy_raw.duplicated(["date"]).sum())
spy = spy_raw.drop_duplicates("date").set_index("date")["close"].sort_index()
cal = pd.DatetimeIndex([d for d in spy.index if START5 <= d <= END])
missing_spy_days = int(len(pd.bdate_range(cal.min(), cal.max())) - len(cal))

# Membership snapshots: latest <= date, duplicates detected.
mem = pd.read_csv(MEMBERS)
mem["date"] = pd.to_datetime(mem.date)
dup_snap = int(mem.duplicated(["date"]).sum())
mem = mem.drop_duplicates("date", keep="last").sort_values("date")
snap_dates = list(mem.date)
members = {d: set(str(t).split(",")) for d, t in zip(mem.date, mem.tickers)}


def members_at(d):
    i = bisect.bisect_right(snap_dates, d) - 1
    return members.get(snap_dates[i], set()) if i >= 0 else set()


# Full expected table: every calendar day x member, including missing prices.
expected = []
for d in cal:
    for s in members_at(d):
        expected.append((s, d))
exp = pd.DataFrame(expected, columns=["ticker", "date"])
exp["year"] = exp.date.dt.year
exp["quarter"] = exp.date.dt.to_period("Q").astype(str)

# Prices: exact symbol/date, no filling.
raw = pd.read_csv(PRICES, usecols=["date", "symbol", "close", "adjusted_close"])
raw["date"] = pd.to_datetime(raw.date)
dup_px = int(raw.duplicated(["symbol", "date"]).sum())
raw = raw.drop_duplicates(["symbol", "date"])
px = raw[raw.date.isin(cal)][["symbol", "date", "close", "adjusted_close"]].rename(columns={"symbol": "ticker"})
exp = exp.merge(px, on=["ticker", "date"], how="left")
exp["observed"] = exp["close"].notna()

member_days = int(len(exp)); observed = int(exp.observed.sum())
coverage = {
    "5Y": {"start": str(cal.min().date()), "end": str(cal.max().date()), "calendar_days": len(cal),
           "expected_member_days": member_days, "observed_member_days": observed,
           "member_day_coverage": observed / member_days if member_days else 0,
           "tickers_expected": int(exp.ticker.nunique()), "tickers_priced": int(exp[exp.observed].ticker.nunique()),
           "ticker_coverage": exp[exp.observed].ticker.nunique() / max(exp.ticker.nunique(), 1),
           "median_names": float(exp[exp.observed].groupby("date").size().median())},
    "calendar": {"spy_duplicate_dates": dup_spy, "weekday_dates_absent_from_spy": missing_spy_days,
                 "membership_duplicate_snapshots": dup_snap, "price_duplicate_symbol_days": dup_px,
                 "snapshot_count": len(snap_dates)},
}
# 3Y subset.
e3 = exp[exp.date >= START3]
coverage["3Y"] = {"start": str(e3.date.min().date()), "end": str(e3.date.max().date()),
                  "calendar_days": int(e3.date.nunique()), "expected_member_days": int(len(e3)),
                  "observed_member_days": int(e3.observed.sum()),
                  "member_day_coverage": float(e3.observed.mean()),
                  "tickers_expected": int(e3.ticker.nunique()), "tickers_priced": int(e3[e3.observed].ticker.nunique()),
                  "ticker_coverage": e3[e3.observed].ticker.nunique() / max(e3.ticker.nunique(), 1),
                  "median_names": float(e3[e3.observed].groupby("date").size().median())}
# Per-stock coverage over full expected membership, including missing-price names.
def stock_table(frame):
    out = []
    for t, g in frame.groupby("ticker"):
        expected_n = len(g); obs = int(g["observed"].sum())
        obs_dates = g[g["observed"]].date
        present = g["observed"].to_numpy(); best = cur = 0
        for v in present:
            cur = 0 if v else cur + 1; best = max(best, cur)
        annual = g.groupby("year")["observed"].mean().round(4).to_dict()
        quarterly = g.groupby("quarter")["observed"].mean().round(4).to_dict()
        out.append({"ticker": t, "expected_member_days": expected_n, "observed_member_days": obs,
                    "coverage": obs / expected_n if expected_n else 0,
                    "first_expected_date": str(g.date.min().date()), "last_expected_date": str(g.date.max().date()),
                    "first_observed_date": str(obs_dates.min().date()) if len(obs_dates) else "",
                    "last_observed_date": str(obs_dates.max().date()) if len(obs_dates) else "",
                    "missing_sessions": expected_n - obs, "longest_missing_streak": best,
                    "annual_coverage": json.dumps(annual), "quarterly_coverage": json.dumps(quarterly)})
    return pd.DataFrame(out).sort_values("coverage")

def make_pools(st):
    return {"broad": st[st.observed_member_days >= 20].ticker.tolist(),
            "cover80": st[st.coverage >= .80].ticker.tolist(),
            "cover95": st[st.coverage >= .95].ticker.tolist(),
            "missing": st[st.observed_member_days == 0].ticker.tolist()}

stock = stock_table(exp); stock.to_csv(OUT / "p13_1_stock_coverage.csv", index=False)
stock3 = stock_table(e3)
pools = make_pools(stock); pools3 = make_pools(stock3)
missing = stock[stock.observed_member_days == 0]
missing.to_csv(OUT / "p13_1_missing_price_members.csv", index=False)
pools["3y_cover95"] = pools3["cover95"]
coverage["pools"] = {k: len(v) for k, v in pools.items()}
coverage["pools_3y"] = {k: len(v) for k, v in pools3.items()}
coverage["missing_price_members"] = len(missing)
(OUT / "p13_1_coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")

# Price panel on the exact market calendar; no fill.
p = exp[exp.observed][["ticker", "date", "close", "adjusted_close"]].copy()
# Use raw close for BOTH stock and SPY because SPY has no adjusted_close.
wide = p.pivot(index="date", columns="ticker", values="close").reindex(cal)
spy_series = spy.reindex(cal)
rows = []
for t in wide.columns:
    s = wide[t].dropna()
    if len(s) < 40: continue
    r = s.reindex(cal)
    logret = np.log(r / r.shift(1))
    vol = logret.rolling(20, min_periods=20).std() * np.sqrt(252)
    mom = r / r.shift(20) - 1
    for i in range(20, len(cal) - 20):
        d = cal[i]; exitd = cal[i + 20]
        if pd.isna(r.iloc[i]) or pd.isna(r.iloc[i + 20]) or pd.isna(spy_series.iloc[i]) or pd.isna(spy_series.iloc[i + 20]):
            continue
        if t not in members_at(d):
            continue
        sr = r.iloc[i + 20] / r.iloc[i] - 1; br = spy_series.iloc[i + 20] / spy_series.iloc[i] - 1
        rows.append({"ticker": t, "signal_date": d, "entry_date": d, "exit_date": exitd,
                     "stock_entry_price": r.iloc[i], "stock_exit_price": r.iloc[i + 20],
                     "benchmark_entry_price": spy_series.iloc[i], "benchmark_exit_price": spy_series.iloc[i + 20],
                     "stock_return": sr, "benchmark_return": br, "excess_return": sr - br,
                     "vol20": vol.iloc[i], "mom20": mom.iloc[i]})
panel = pd.DataFrame(rows)
panel.to_csv(OUT / "p13_1_aligned_panel.csv", index=False)
# sample alignment check 20 rows
panel.sample(20, random_state=13).to_csv(OUT / "p13_1_alignment_sample.csv", index=False)
# Cohort daily IC/spread.
def cohort_daily(panel, tickers, label):
    g = panel[panel.ticker.isin(tickers)].dropna(subset=["vol20", "mom20", "excess_return"])
    out = []
    for d, x in g.groupby("signal_date"):
        if len(x) < 30: continue
        row = {"date": d, "n": len(x)}
        for f in ("vol20", "mom20"):
            row[f"ic_{f}"] = stats.spearmanr(x[f], x.excess_return).statistic
            q = pd.qcut(x[f].rank(method="first"), 5, labels=False)
            row[f"spread_{f}"] = x.excess_return[q == 4].mean() - x.excess_return[q == 0].mean()
        out.append(row)
    return pd.DataFrame(out)

results = []; oos = []; boot = []
for label, start in (("5Y", START5), ("3Y", START3)):
    pnl = panel[panel.signal_date >= start]
    poolset = pools if label == "5Y" else pools3
    for cohort in ("broad", "cover80", "cover95"):
        d = cohort_daily(pnl, set(poolset[cohort]), label)
        if d.empty: continue
        for f in ("vol20", "mom20"):
            x = d[f"spread_{f}"].dropna(); t = nw(x, 19)
            results.append({"window": label, "cohort": cohort, "factor": f, "direction": "high_minus_low",
                            "dates": len(x), "mean_ic": d[f"ic_{f}"].mean(), "mean_spread": x.mean(),
                            "hac_lag19_t": t, "p": 2 * stats.t.sf(abs(t), len(x) - 1)})
            # 20-day moving block bootstrap
            arr = x.to_numpy(); rng = np.random.default_rng(20261119); means = []
            nblocks = int(np.ceil(len(arr) / 20))
            for _ in range(2000):
                idx = rng.integers(0, len(arr) - 19, nblocks)
                means.append(np.concatenate([arr[i:i + 20] for i in idx]).mean())
            boot.append({"window": label, "cohort": cohort, "factor": f, "blocks": nblocks,
                         "boot_low": float(np.quantile(means, .025)), "boot_high": float(np.quantile(means, .975))})
        # OOS purge by signal date; 20D labels may not cross next split.
        dates = sorted(d.date.unique()); c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
        b1, b2 = dates[c1], dates[c2]
        def purge(seg_dates, boundary):
            keep = []
            for ds in seg_dates:
                pos = cal.get_loc(ds)
                if pos + 20 < len(cal) and cal[pos + 20] < boundary:
                    keep.append(ds)
            return keep
        tr = purge(dates[:c1], b1); va = purge(dates[c1:c2], b2); te = dates[c2:]
        for seg, ss in (("train", tr), ("validation", va), ("test", te)):
            sub = d[d.date.isin(ss)]
            subp = pnl[pnl.signal_date.isin(ss)]
            exits = subp.exit_date
            boundary = b1 if seg == "train" else (b2 if seg == "validation" else None)
            last_exit = exits.max() if len(exits) else pd.NaT
            purge_ok = bool(last_exit < boundary) if boundary is not None and len(exits) else (len(exits) > 0)
            for f in ("vol20", "mom20"):
                oos.append({"window": label, "cohort": cohort, "segment": seg, "factor": f, "dates": len(sub),
                            "start": str(min(ss).date()) if ss else "", "end": str(max(ss).date()) if ss else "",
                            "entry_min": str(subp.entry_date.min().date()) if len(subp) else "",
                            "exit_min": str(exits.min().date()) if len(exits) else "",
                            "exit_max": str(last_exit.date()) if len(exits) else "",
                            "next_segment_first_signal": str(boundary.date()) if boundary is not None else "",
                            "exit_before_next_boundary": purge_ok,
                            "mean_ic": sub[f"ic_{f}"].mean(), "mean_spread": sub[f"spread_{f}"].mean()})
res = pd.DataFrame(results)
res["q"] = res.groupby("window")["p"].transform(lambda x: bh(x))
res.to_csv(OUT / "p13_1_price_hac.csv", index=False)
pd.DataFrame(boot).to_csv(OUT / "p13_1_block_bootstrap.csv", index=False)
pd.DataFrame(oos).to_csv(OUT / "p13_1_price_oos.csv", index=False)
summary = {"coverage": coverage, "pools": {k: len(v) for k, v in pools.items()},
           "alignment": {"rows": len(panel), "sample_rows": 20,
                         "entry_exit_same_calendar": bool((panel.entry_date == panel.signal_date).all()),
                         "return_basis": "CLOSE_PRICE_ONLY_ADJUSTMENT_UNVERIFIED"},
           "price_results": res.to_dict("records"), "bootstrap": boot, "oos": oos,
           "quality": "DATA_BLOCKED", "status": "P13_1_1_COMPLETE"}
(OUT / "p13_1_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
# hashes
files = {}
for f in OUT.iterdir():
    if f.suffix in {".csv", ".json"} and f.name != "p13_1_manifest.json":
        files[f.name] = {"sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "bytes": f.stat().st_size}
(OUT / "p13_1_manifest.json").write_text(json.dumps({"outputs": files, "note": "P13.1.1 corrected"}, indent=2), encoding="utf-8")
print(json.dumps({k: summary[k] for k in ("coverage", "pools", "alignment")}, indent=2, default=str))
print(res.sort_values("p").head(8).to_string(index=False))
