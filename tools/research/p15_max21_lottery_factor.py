#!/usr/bin/env python3
"""P15 MAX21 lottery-demand factor research, local data only."""
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


def boot(x, reps=2000, block=21, seed=20261120):
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
    raw = raw.drop_duplicates(["symbol", "date"]).dropna()
    all_dates = pd.DatetimeIndex(sorted(raw.date.unique()))
    mat = raw.pivot(index="date", columns="symbol", values="adjusted_close").sort_index().reindex(all_dates)
    rets = mat.pct_change()
    max21 = rets.rolling(21, min_periods=21).max()
    rv21 = rets.rolling(21, min_periods=21).std() * np.sqrt(252)
    fwd = mat.shift(-22) / mat.shift(-1) - 1
    cal = all_dates[(all_dates >= "2020-01-02") & (all_dates <= "2024-12-31")]
    mem = pd.read_csv(a.members); mem["date"] = pd.to_datetime(mem.date)
    snap = list(mem.date); mm = {d: set(str(t).split(",")) for d, t in zip(mem.date, mem.tickers)}
    import bisect
    def members_at(d):
        i = bisect.bisect_right(snap, d) - 1
        return mm.get(snap[i], set()) if i >= 0 else set()
    rows = []
    for i, d in enumerate(all_dates):
        if d < cal[0] or d > cal[-1] or i + 22 >= len(all_dates): continue
        s = set(members_at(d))
        for t in s:
            if t not in max21.columns: continue
            m, rv, f = max21.at[d, t], rv21.at[d, t], fwd.at[d, t]
            if pd.notna(m) and pd.notna(rv) and pd.notna(f):
                rows.append({"ticker": t, "signal_date": d, "entry_date": all_dates[i + 1], "exit_date": all_dates[i + 22],
                             "max21": float(m), "rv21": float(rv), "forward_21": float(f),
                             "entry_price": mat.at[all_dates[i + 1], t], "exit_price": mat.at[all_dates[i + 22], t]})
    p = pd.DataFrame(rows)
    daily = []; fm = []
    for d, g in p.groupby("signal_date"):
        if len(g) < 50: continue
        q = pd.qcut(g.max21.rank(method="first"), 5, labels=False)
        row = {"date": d, "n": len(g), "ic": stats.spearmanr(g.max21, g.forward_21).statistic,
               "q1": g.forward_21[q == 0].mean(), "q2": g.forward_21[q == 1].mean(), "q3": g.forward_21[q == 2].mean(),
               "q4": g.forward_21[q == 3].mean(), "q5": g.forward_21[q == 4].mean()}
        row["spread"] = row["q1"] - row["q5"]
        daily.append(row)
        z1 = (g.max21 - g.max21.mean()) / g.max21.std(ddof=0)
        z2 = (g.rv21 - g.rv21.mean()) / g.rv21.std(ddof=0)
        X = np.column_stack([np.ones(len(g)), z1, z2]); y = g.forward_21.to_numpy()
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        fm.append({"date": d, "beta_max": coef[1], "beta_rv": coef[2]})
    d = pd.DataFrame(daily); fm = pd.DataFrame(fm)
    t = nw(d.spread, 20); lo, hi = boot(d.spread)
    bmax = nw(fm.beta_max, 20); brv = nw(fm.beta_rv, 20)
    summary = {"rows": len(p), "dates": len(d), "tickers": int(p.ticker.nunique()),
               "ic": float(d.ic.mean()), "q1_minus_q5": float(d.spread.mean()), "hac_t": float(t),
               "hac_p": float(2 * stats.t.sf(abs(t), len(d) - 1)), "boot_low": lo, "boot_high": hi,
               "fm_beta_max": float(fm.beta_max.mean()), "fm_beta_max_t": float(bmax),
               "fm_beta_max_p": float(2 * stats.t.sf(abs(bmax), len(fm) - 1)),
               "fm_beta_rv": float(fm.beta_rv.mean()), "fm_beta_rv_t": float(brv),
               "corr_max_rv": float(p.max21.corr(p.rv21)), "monthly": [], "costs": [], "oos": []}
    # OOS purge
    dates = list(d.date); c1, c2 = int(len(dates) * .6), int(len(dates) * .8)
    b1, b2 = dates[c1], dates[c2]
    def keep(seg, boundary):
        return [x for x in seg if all_dates.get_loc(x) + 22 < len(all_dates) and all_dates[all_dates.get_loc(x) + 22] < boundary]
    for label, seg, boundary in (("train", dates[:c1], b1), ("validation", dates[c1:c2], b2), ("test", dates[c2:], None)):
        if boundary is not None: seg = keep(seg, boundary)
        sub = d[d.date.isin(seg)]
        tt = nw(sub.spread, 20) if len(sub) > 5 else np.nan
        summary["oos"].append({"segment": label, "dates": len(sub), "start": str(min(seg).date()), "end": str(max(seg).date()),
                               "ic": float(sub.ic.mean()), "q1_minus_q5": float(sub.spread.mean()),
                               "hac_t": float(tt), "p": float(2 * stats.t.sf(abs(tt), len(sub) - 1)) if np.isfinite(tt) else None})
    # fixed non-overlapping 21-session long-only bottom 20%
    sigs = [cal[0]]
    while sigs[-1] + pd.Timedelta(days=1) <= cal[-1]:
        pos = all_dates.get_loc(sigs[-1]); nxt = pos + 21
        if nxt >= len(all_dates) or all_dates[nxt] > cal[-1]: break
        sigs.append(all_dates[nxt])
    prev = {}; prev_e = {}; monthly = []
    for s in sigs:
        g = p[p.signal_date == s]
        if len(g) < 50: continue
        bot = g.nsmallest(max(1, int(len(g) * .2)), "max21")
        ew = g.forward_21.mean(); top = bot.forward_21.mean()
        w = {t: 1 / len(bot) for t in bot.ticker}; wew = {t: 1 / len(g) for t in g.ticker}
        turn_t = sum(abs(w.get(t, 0) - prev.get(t, 0)) for t in set(w) | set(prev))
        turn_e = sum(abs(wew.get(t, 0) - prev_e.get(t, 0)) for t in set(wew) | set(prev_e))
        monthly.append({"date": s, "n": len(g), "n_bottom": len(bot), "long_return": top, "ew_return": ew,
                        "gross_excess": top - ew, "turnover_long": turn_t, "turnover_ew": turn_e,
                        "holdings": list(bot.ticker)})
        prev = w; prev_e = wew
    m = pd.DataFrame(monthly)
    if len(m):
        m["cum_long"] = (1 + m.long_return).cumprod(); m["cum_ew"] = (1 + m.ew_return).cumprod()
        m["dd_long"] = m.cum_long / m.cum_long.cummax() - 1
        for bps in (5, 10, 20):
            cl = bps / 1e4 * m.turnover_long; ce = bps / 1e4 * m.turnover_ew
            summary["costs"].append({"bps_per_side": bps, "long_net_mean": float((m.long_return - cl).mean()),
                                     "ew_net_mean": float((m.ew_return - ce).mean()),
                                     "net_excess": float(((m.long_return - cl) - (m.ew_return - ce)).mean()),
                                     "avg_turnover_long": float(m.turnover_long.mean())})
        summary["monthly_stats"] = {"periods": len(m), "mean_long": float(m.long_return.mean()),
                                    "mean_ew": float(m.ew_return.mean()), "gross_excess": float(m.gross_excess.mean()),
                                    "cum_long": float(m.cum_long.iloc[-1]), "cum_ew": float(m.cum_ew.iloc[-1]),
                                    "max_dd_long": float(m.dd_long.min())}
    v = {"rows": len(p), "dates": len(d), "tickers": int(p.ticker.nunique()),
         "price_basis": "adjusted_close", "adjustment": "ADJUSTMENT_UNVERIFIED",
         "max21_requires": 22, "first_signal": str(cal[0].date()), "first_has_formation": bool(max21.loc[cal[0]].notna().any())}
    (a.out / "p15_data_coverage.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
    (a.out / "p15_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    d.to_csv(a.out / "p15_daily_ic.csv", index=False); p.to_csv(a.out / "p15_max21_signal_panel.csv", index=False)
    fm.to_csv(a.out / "p15_fama_macbeth.csv", index=False); m.drop(columns=["holdings"], errors="ignore").to_csv(a.out / "p15_monthly_long_only.csv", index=False)
    pd.DataFrame(summary["oos"]).to_csv(a.out / "p15_oos_results.csv", index=False)
    pd.DataFrame(summary["costs"]).to_csv(a.out / "p15_cost_sensitivity.csv", index=False)
    pd.DataFrame([{"hac_lag20_t": t, "p": summary["hac_p"], "q1_minus_q5": d.spread.mean()}]).to_csv(a.out / "p15_hac_results.csv", index=False)
    pd.DataFrame([{"boot_low": lo, "boot_high": hi, "reps": 2000, "block": 21, "seed": 20261120}]).to_csv(a.out / "p15_block_bootstrap.csv", index=False)
    pd.DataFrame([{"fm_beta_max": summary["fm_beta_max"], "t": bmax, "p": summary["fm_beta_max_p"],
                   "fm_beta_rv": summary["fm_beta_rv"], "rv_t": brv}]).to_csv(a.out / "p15_fm_results.csv", index=False)
    files = {}
    for f in a.out.iterdir():
        if f.suffix in {".csv", ".json"}:
            files[f.name] = {"sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "bytes": f.stat().st_size}
    (a.out / "p15_manifest.json").write_text(json.dumps({"outputs": files, "note": "P15 local-only panel not committed"}, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("rows", "dates", "tickers", "ic", "q1_minus_q5", "hac_t", "hac_p", "boot_low", "boot_high", "fm_beta_max", "fm_beta_max_t", "fm_beta_rv", "corr_max_rv", "monthly_stats", "costs")}, indent=2, default=str))


if __name__ == "__main__":
    main()
