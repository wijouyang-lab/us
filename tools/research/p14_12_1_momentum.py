#!/usr/bin/env python3
"""P14 12-1 momentum research. Local data only; no orders."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def nw(x, lag=20):
    x = np.asarray(x, float); n = len(x); e = x - x.mean(); v = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(v / n) if v > 0 else np.nan


def block_boot(x, reps=2000, block=21, seed=20261119):
    x = np.asarray(x, float); rng = np.random.default_rng(seed); nb = int(np.ceil(len(x) / block)); out = []
    for _ in range(reps):
        starts = rng.integers(0, len(x) - block + 1, nb)
        out.append(np.concatenate([x[s:s + block] for s in starts]).mean())
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", type=Path, required=True)
    ap.add_argument("--members", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(a.prices, usecols=["date", "symbol", "close", "adjusted_close"])
    raw["date"] = pd.to_datetime(raw.date)
    dup = int(raw.duplicated(["symbol", "date"]).sum())
    raw = raw.drop_duplicates(["symbol", "date"]).dropna()
    cal = pd.DatetimeIndex(sorted(raw.date.unique()))
    cal = cal[(cal >= "2020-01-02") & (cal <= "2024-12-31")]
    # full history matrix: factor lookback before membership is allowed
    all_dates = pd.DatetimeIndex(sorted(raw.date.unique()))
    mat = raw.pivot(index="date", columns="symbol", values="adjusted_close").sort_index()
    mat = mat.reindex(all_dates)
    mom = mat.shift(21) / mat.shift(252) - 1
    fwd = mat.shift(-22) / mat.shift(-1) - 1
    mem = pd.read_csv(a.members); mem["date"] = pd.to_datetime(mem.date)
    snap = list(mem.date); mm = {d: set(str(t).split(",")) for d, t in zip(mem.date, mem.tickers)}
    import bisect
    def members_at(d):
        i = bisect.bisect_right(snap, d) - 1
        return mm.get(snap[i], set()) if i >= 0 else set()
    rows = []
    for i, d in enumerate(cal):
        if i < 252 or i + 22 >= len(cal): continue
        s = set(members_at(d))
        m = mom.loc[d]; f = fwd.loc[d]
        for t in s:
            if t in m.index and pd.notna(m[t]) and pd.notna(f.get(t, np.nan)):
                rows.append({"ticker": t, "signal_date": d, "entry_date": cal[i + 1], "exit_date": cal[i + 22],
                             "mom_12_1": float(m[t]), "forward_21": float(f[t])})
    p = pd.DataFrame(rows)
    daily = []
    for d, g in p.groupby("signal_date"):
        if len(g) < 50: continue
        ic = stats.spearmanr(g.mom_12_1, g.forward_21).statistic
        q = pd.qcut(g.mom_12_1.rank(method="first"), 5, labels=False)
        daily.append({"date": d, "n": len(g), "ic": ic, "q1": g.forward_21[q == 0].mean(),
                      "q2": g.forward_21[q == 1].mean(), "q3": g.forward_21[q == 2].mean(),
                      "q4": g.forward_21[q == 3].mean(), "q5": g.forward_21[q == 4].mean(),
                      "spread": g.forward_21[q == 4].mean() - g.forward_21[q == 0].mean()})
    d = pd.DataFrame(daily)
    t = nw(d.spread, 20)
    low, high = block_boot(d.spread)
    summary = {"rows": len(p), "dates": len(d), "tickers": int(p.ticker.nunique()),
               "ic_mean": float(d.ic.mean()), "q5_minus_q1": float(d.spread.mean()),
               "hac_lag20_t": float(t), "hac_p": float(2 * stats.t.sf(abs(t), len(d) - 1)),
               "boot_low": low, "boot_high": high, "monthly": [], "costs": [], "oos": []}
    # chronological OOS with 21D purge
    dates = list(d.date); c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
    b1, b2 = dates[c1], dates[c2]
    def keep(seg, boundary):
        out = []
        for x in seg:
            pos = cal.get_loc(x)
            if pos + 22 < len(cal) and cal[pos + 22] < boundary: out.append(x)
        return out
    for label, seg, boundary in (("train", dates[:c1], b1), ("validation", dates[c1:c2], b2), ("test", dates[c2:], None)):
        if boundary is not None: seg = keep(seg, boundary)
        sub = d[d.date.isin(seg)]
        tt = nw(sub.spread, 20) if len(sub) > 5 else np.nan
        summary["oos"].append({"segment": label, "dates": len(sub), "start": str(min(seg).date()), "end": str(max(seg).date()),
                               "ic": float(sub.ic.mean()), "spread": float(sub.spread.mean()),
                               "hac_t": float(tt), "p": float(2 * stats.t.sf(abs(tt), len(sub) - 1)) if np.isfinite(tt) else None})
    # monthly non-overlapping long-only
    reb = list(range(0, len(cal) - 22, 21)); prev = set(); monthly = []
    for j in reb:
        d0 = cal[j]; i = list(cal).index(d0)
        if d0 < pd.Timestamp("2020-02-01") or i + 22 >= len(cal): continue
        g = p[p.signal_date == d0]
        if len(g) < 50: continue
        top = g.nlargest(max(1, int(len(g) * .2)), "mom_12_1")
        ew = g.forward_21.mean(); topret = top.forward_21.mean()
        now = set(top.ticker); added = len(now - prev); removed = len(prev - now)
        turnover = (added + removed) / (2 * max(len(now), 1)) if prev else 1.0
        monthly.append({"date": d0, "n": len(g), "n_top": len(top), "top_return": topret, "ew_return": ew,
                        "excess": topret - ew, "turnover": turnover, "holdings": len(now)})
        prev = now
    m = pd.DataFrame(monthly)
    if len(m):
        m["cum_top"] = (1 + m.top_return).cumprod()
        m["cum_ew"] = (1 + m.ew_return).cumprod()
        m["dd_top"] = m.cum_top / m.cum_top.cummax() - 1
        summary["monthly"] = m.to_dict("records")
        for bps in (5, 10, 20):
            net = m.top_return - 2 * bps / 1e4 * m.turnover
            summary["costs"].append({"bps_per_side": bps, "gross_mean": float(m.top_return.mean()),
                                     "net_mean": float(net.mean()), "ew_mean": float(m.ew_return.mean()),
                                     "net_excess": float((net - m.ew_return).mean()),
                                     "trades": int(m.n_top.sum()), "avg_turnover": float(m.turnover.mean())})
    v = {"rows": len(p), "dates": len(d), "tickers": int(p.ticker.nunique()), "duplicate_symbol_dates": dup,
         "price_basis": "adjusted_close", "adjustment": "ADJUSTMENT_UNVERIFIED"}
    (a.out / "p14_data_coverage.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
    (a.out / "p14_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    d.to_csv(a.out / "p14_daily_ic.csv", index=False); p.to_csv(a.out / "p14_momentum_signal_panel.csv", index=False)
    m.to_csv(a.out / "p14_monthly_long_only.csv", index=False)
    pd.DataFrame(summary["costs"]).to_csv(a.out / "p14_cost_sensitivity.csv", index=False)
    pd.DataFrame(summary["oos"]).to_csv(a.out / "p14_oos_results.csv", index=False)
    pd.DataFrame([{"hac_lag20_t": t, "p": summary["hac_p"], "ic_mean": d.ic.mean(), "spread": d.spread.mean()}]).to_csv(a.out / "p14_hac_results.csv", index=False)
    pd.DataFrame([{"boot_low": low, "boot_high": high, "reps": 2000, "block": 21, "seed": 20261119}]).to_csv(a.out / "p14_block_bootstrap.csv", index=False)
    files = {}
    for f in a.out.iterdir():
        if f.suffix in {".csv", ".json"}:
            files[f.name] = {"sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "bytes": f.stat().st_size}
    (a.out / "p14_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("rows", "dates", "tickers", "ic_mean", "q5_minus_q1", "hac_lag20_t", "hac_p", "boot_low", "boot_high", "costs")}, indent=2, default=str))


if __name__ == "__main__":
    main()
