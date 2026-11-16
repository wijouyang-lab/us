"""P11.2 price-factor study on the restricted S&P 500 panel.

Requires local raw data via --base. Results are aggregate; no raw data is written.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

FACTORS = [
    "mom5", "mom10", "mom20", "mom60", "mom120",
    "rs20", "rs60", "rs120",
    "slope20", "slope60", "slope120",
    "vol_anom20", "volume_price_corr20",
    "vol20", "vol60", "vol_change", "risk_adj_mom20",
    "dd20", "dd60", "dd120",
]
HORIZONS = (5, 10, 20)
PERIODS = {"dev": ("2000-01-03", "2012-12-31"), "val": ("2013-01-01", "2017-12-31"), "oos": ("2018-01-01", "2024-12-31")}
COST_BPS = 20.0
INDEPENDENT_FACTORS = 17
OUT_PREFIX = "p11_2_2"


def hac_t(values, lag: int) -> float:
    s = pd.Series(values).dropna()
    n = len(s)
    if n < 10:
        return float("nan")
    mean = float(s.mean())
    d = s - mean
    var = float((d * d).mean())
    for l in range(1, min(lag, n - 1) + 1):
        g = float((d.iloc[l:].reset_index(drop=True) * d.iloc[:-l].reset_index(drop=True)).mean())
        var += 2 * (1 - l / (lag + 1)) * g
    se = math.sqrt(max(var, 0) / n)
    return mean / se if se else float("nan")


def p_two_sided(t: float) -> float:
    return math.erfc(abs(t) / math.sqrt(2)) if np.isfinite(t) else float("nan")


def bh_q(pvals: list[float]) -> list[float]:
    out = [float("nan")] * len(pvals)
    valid = [(i, p) for i, p in enumerate(pvals) if np.isfinite(p)]
    m = len(valid)
    ordered = sorted(valid, key=lambda x: x[1])
    prev = 1.0
    for rank in range(m, 0, -1):
        i, p = ordered[rank - 1]
        prev = min(prev, p * m / rank)
        out[ordered[rank - 1][0]] = prev
    return out


def _membership_mask(base: Path, dates: pd.DatetimeIndex, tickers: pd.Index) -> pd.DataFrame:
    mem = pd.read_csv(base / "historical_universe/sp500_daily.csv", parse_dates=["date"]).drop_duplicates("date").sort_values("date")
    snaps = [(r.date.date(), {x.strip().upper().replace(".", "-") for x in str(r.tickers).split(",") if x.strip()}) for r in mem.itertuples()]
    sd = [x[0] for x in snaps]
    import bisect
    mask = pd.DataFrame(False, index=dates, columns=tickers)
    for d in dates:
        i = bisect.bisect_right(sd, d.date()) - 1
        if i >= 0:
            names = [t for t in snaps[i][1] if t in tickers]
            mask.loc[d, names] = True
    return mask


def build_factors(base: Path) -> tuple[dict, dict, pd.DataFrame, pd.DataFrame]:
    px = pd.read_csv(base / "pit_data/finsaber_prices_raw.csv", usecols=["date", "symbol", "open", "close", "adjusted_close", "volume"], parse_dates=["date"])
    px = px[(px.date >= "2000-01-03") & (px.date <= "2024-12-31")].copy()
    px["symbol"] = px.symbol.str.upper().str.replace(".", "-", regex=False)
    px["adj_factor"] = px.adjusted_close / px.close.replace(0, np.nan)
    px["open_adj"] = px.open * px.adj_factor
    close = px.pivot_table(index="date", columns="symbol", values="adjusted_close", aggfunc="last").sort_index()
    open_adj = px.pivot_table(index="date", columns="symbol", values="open_adj", aggfunc="last").sort_index()
    volume = px.pivot_table(index="date", columns="symbol", values="volume", aggfunc="last").sort_index()
    ret = close.pct_change(fill_method=None)
    spy = pd.read_csv(base / "p9_1_support_resistance/spy.csv", parse_dates=["Date"]).set_index("Date").sort_index()["close"]
    spy = spy.reindex(close.index).ffill()
    factors = {}
    for n in (5, 10, 20, 60, 120):
        factors[f"mom{n}"] = close / close.shift(n) - 1
    logp = np.log(close)
    idx = pd.Series(np.arange(len(close)), index=close.index)
    for n in (20, 60, 120):
        factors[f"rs{n}"] = factors[f"mom{n}"].sub(spy / spy.shift(n) - 1, axis=0)
        # True rolling OLS slope of log price on local t=0..n-1, annualized.
        st = n * (n - 1) / 2
        stt = n * (n - 1) * (2 * n - 1) / 6
        sy = logp.rolling(n).sum()
        swy = logp.mul(idx, axis=0).rolling(n).sum()
        start = idx - (n - 1)
        sxy = swy.sub(sy.mul(start, axis=0))
        denom = n * stt - st * st
        factors[f"slope{n}"] = (n * sxy - st * sy) / denom * 252
        factors[f"dd{n}"] = close / close.rolling(n).max() - 1
    factors["vol_anom20"] = volume / volume.rolling(20).mean() - 1
    factors["volume_price_corr20"] = ret.rolling(20).corr(volume.pct_change(fill_method=None))
    factors["vol20"] = ret.rolling(20).std() * np.sqrt(252)
    factors["vol60"] = ret.rolling(60).std() * np.sqrt(252)
    factors["vol_change"] = factors["vol20"] - factors["vol60"]
    factors["risk_adj_mom20"] = factors["mom20"] / factors["vol20"].replace(0, np.nan)
    fwd = {}
    spy_fwd = {}
    for h in HORIZONS:
        fwd[h] = close.shift(-h) / open_adj.shift(-1) - 1
        spy_fwd[h] = spy.shift(-h) / spy.shift(-1) - 1
    mask = _membership_mask(base, close.index, close.columns)
    return factors, fwd, spy_fwd, close, mask


def evaluate(factors: dict, fwd: dict, spy_fwd: dict, close: pd.DataFrame, mask: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = close.index
    cols = list(close.columns)
    M = mask.to_numpy(dtype=bool)
    rows, annual_rows, quint_rows = [], [], []
    for f in FACTORS:
        X = factors[f].to_numpy(dtype=float)
        for h in HORIZONS:
            Y = fwd[h].to_numpy(dtype=float)
            S = spy_fwd[h].to_numpy(dtype=float)
            E = Y - S[:, None]
            ics_raw, ics_exc, rics, ls_raw, ls_exc, top_raw, top_exc, turns = [], [], [], [], [], [], [], []
            eval_dates = []
            missing_obs = 0
            missing_top = 0
            incomplete_top = 0
            quintile_missing = 0
            quintile_incomplete = 0
            extreme_obs = 0
            coverages = []
            prev_top = set()
            for i, d in enumerate(dates):
                eligible = M[i] & np.isfinite(X[i])
                if eligible.sum() < 30:
                    continue
                available = eligible & np.isfinite(Y[i]) & np.isfinite(E[i])
                missing_obs += int(eligible.sum() - available.sum())
                extreme_obs += int((eligible & np.isfinite(Y[i]) & (Y[i] > 5.0)).sum())
                coverages.append(available.sum() / eligible.sum())
                if available.sum() < 30:
                    continue
                xv = X[i][eligible]
                yv = Y[i][available]
                ev = E[i][available]
                xw = np.clip(xv, np.nanquantile(xv, 0.01), np.nanquantile(xv, 0.99))
                yw = np.clip(yv, np.nanquantile(yv, 0.01), np.nanquantile(yv, 0.99))
                ew = np.clip(ev, np.nanquantile(ev, 0.01), np.nanquantile(ev, 0.99))
                avail_local = np.isfinite(Y[i][eligible])
                xw_ic = xw[avail_local]
                q = pd.qcut(xw, 5, labels=False, duplicates="drop")
                if len(np.unique(q)) < 5:
                    continue
                ics_raw.append(np.corrcoef(xw_ic, yw)[0, 1])
                ics_exc.append(np.corrcoef(xw_ic, ew)[0, 1])
                rics.append(np.corrcoef(pd.Series(xw_ic).rank(), pd.Series(yw).rank())[0, 1])
                eval_dates.append(d)
                graw = pd.Series(Y[i][eligible]).groupby(q).apply(lambda z: z.mean() if z.notna().all() else np.nan)
                gexc = pd.Series(E[i][eligible]).groupby(q).apply(lambda z: z.mean() if z.notna().all() else np.nan)
                quintile_missing += int(graw.isna().sum())
                if graw.isna().any():
                    quintile_incomplete += 1
                quint_rows.append({"factor": f, "horizon": h, "date": d, **{f"q{j+1}": float(graw.get(j, np.nan)) for j in range(5)}})
                ls_raw.append(float(graw.get(4, np.nan) - graw.get(0, np.nan)))
                ls_exc.append(float(gexc.get(4, np.nan) - gexc.get(0, np.nan)))
                k = max(1, int(math.ceil(eligible.sum() * 0.10)))
                idx = np.argsort(-xv)[:k]
                ytop = Y[i][eligible][idx]
                etop = E[i][eligible][idx]
                missing = int(np.isnan(ytop).sum() + np.isnan(etop).sum())
                missing_top += missing
                if missing or len(ytop) == 0:
                    incomplete_top += 1
                    top_raw.append(np.nan); top_exc.append(np.nan)
                else:
                    top_raw.append(float(np.mean(ytop))); top_exc.append(float(np.mean(etop)))
                names = set(np.array(cols)[eligible][idx])
                turns.append(1 - len(names & prev_top) / max(1, len(names)))
                prev_top = names
            if not ics_raw:
                continue
            ic_r = pd.Series(ics_raw, index=pd.to_datetime(eval_dates))
            ic_e = pd.Series(ics_exc, index=ic_r.index)
            cost = (np.nanmean(turns) if turns else np.nan) * COST_BPS / 10000
            tr = hac_t(ic_r, max(1, h - 1)); te = hac_t(ic_e, max(1, h - 1))
            # Fixed calendar sampling: every h-th full trading date, never compress after dropping.
            sampled_dates = [d for d in dates[::h] if d in ic_r.index]
            nonoverlap = ic_r.loc[sampled_dates]
            rows.append({
                "factor": f, "horizon": h, "n_days": len(ic_r),
                "mean_ic_raw": ic_r.mean(), "mean_rank_ic_raw": np.mean(rics),
                "ic_hac_t_raw": tr, "ic_p_raw": p_two_sided(tr),
                "mean_ic_excess": ic_e.mean(), "ic_hac_t_excess": te, "ic_p_excess": p_two_sided(te),
                "nonoverlap_ic_raw": nonoverlap.mean(), "nonoverlap_t_raw": hac_t(nonoverlap, 0), "nonoverlap_n": len(nonoverlap),
                "q5_minus_q1_raw": np.nanmean(ls_raw), "ls_hac_t_raw": hac_t(pd.Series(ls_raw), max(1, h - 1)),
                "q5_minus_q1_excess": np.nanmean(ls_exc), "ls_hac_t_excess": hac_t(pd.Series(ls_exc), max(1, h - 1)),
                "top10_raw": np.nanmean(top_raw), "top10_hac_t_raw": hac_t(pd.Series(top_raw), max(1, h - 1)),
                "top10_excess_raw": np.nanmean(top_exc), "top10_excess_hac_t": hac_t(pd.Series(top_exc), max(1, h - 1)),
                "avg_turnover": np.nanmean(turns), "cost_bps_est": cost * 10000,
                "net_top10_raw": np.nanmean(top_raw) - cost, "net_top10_excess": np.nanmean(top_exc) - cost,
                "return_coverage": float(np.nanmean(coverages)), "return_coverage_ok": bool(np.nanmean(coverages) >= 0.95),
                "missing_return_obs": missing_obs, "top10_missing_values": missing_top,
                "top10_incomplete_days": incomplete_top, "top10_complete_days": len(ic_r) - incomplete_top,
                "quintile_missing_values": quintile_missing, "quintile_incomplete_days": quintile_incomplete,
                "extreme_positive_obs": extreme_obs,
            })
            for period, (a, b) in PERIODS.items():
                mm = (ic_r.index >= a) & (ic_r.index <= b)
                annual_rows.append({"factor": f, "horizon": h, "period": period, "mean_ic_raw": ic_r[mm].mean(), "mean_ic_excess": ic_e[mm].mean(), "ls_raw": np.nanmean(np.array(ls_raw)[mm]), "ls_excess": np.nanmean(np.array(ls_exc)[mm]), "n_days": int(mm.sum())})
    res = pd.DataFrame(rows)
    res["bh_q_raw"] = bh_q(res["ic_p_raw"].tolist())
    res["bh_q_excess"] = bh_q(res["ic_p_excess"].tolist())
    corr_rows = []
    for i in range(0, len(dates), 20):
        g = pd.DataFrame({f: factors[f].iloc[i] for f in FACTORS})
        g = g[M[i] & np.isfinite(g).all(axis=1)]
        if len(g) >= 30:
            corr_rows.append(g.rank().corr())
    corr = pd.concat(corr_rows).groupby(level=0).mean() if corr_rows else pd.DataFrame()
    return res, pd.DataFrame(annual_rows), pd.DataFrame(quint_rows), corr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    factors, fwd, spy_fwd, close, mask = build_factors(args.base)
    res, annual, quint, corr = evaluate(factors, fwd, spy_fwd, close, mask)
    res.to_csv(args.out / "p11_2_2_factor_results.csv", index=False)
    annual.to_csv(args.out / "p11_2_2_annual_ic.csv", index=False)
    quint = quint.groupby(["factor", "horizon"], as_index=False)[["q1", "q2", "q3", "q4", "q5"]].mean()
    quint.to_csv(args.out / "p11_2_2_quintile_returns.csv", index=False)
    corr.to_csv(args.out / "p11_2_2_factor_correlation.csv")
    catalog = []
    for f in FACTORS:
        dup = next((m for m in ("mom20", "mom60", "mom120") if f == "rs" + m[3:]), None)
        catalog.append({"factor": f, "raw_factor": True, "independent": dup is None, "duplicate_of": dup or "", "note": "RS rank is identical to matching MOM; retained as diagnostic only" if dup else ""})
    pd.DataFrame(catalog).to_csv(args.out / "p11_2_2_factor_catalog.csv", index=False)
    config = {"version": "2.2", "factors": FACTORS, "independent_factors": INDEPENDENT_FACTORS, "horizons": list(HORIZONS), "periods": PERIODS, "cost_bps_roundtrip": COST_BPS, "cost_model": "SIMPLIFIED_20BPS_ROUNDTRIP_NOT_IBKR", "membership": "PIT snapshot expansion", "execution": "next adjusted open to adjusted close", "benchmark": "SPY close-to-close proxy; raw returns primary", "benchmark_fair_comparison": False, "universe": "S&P 500 price panel / PIT filtered", "sample_selection": "same-day signal + membership only; Y not used for eligibility", "winsorization": "IC diagnostics only; portfolio returns raw", "synthetic": False}
    (args.out / "p11_2_2_experiment_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    summary = {"rows": len(res), "raw_factors": len(FACTORS), "independent_factors": INDEPENDENT_FACTORS, "horizons": len(HORIZONS), "universe_tickers": int(close.shape[1]), "status": "COMPUTED", "benchmark_fair": False, "cost_model": "SIMPLIFIED"}
    (args.out / "p11_2_2_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
