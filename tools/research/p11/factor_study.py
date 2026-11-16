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
    for n in (20, 60, 120):
        factors[f"rs{n}"] = factors[f"mom{n}"].sub(spy / spy.shift(n) - 1, axis=0)
        factors[f"slope{n}"] = (close - close.shift(n)) / (n * close.shift(n))
        factors[f"dd{n}"] = close / close.rolling(n).max() - 1
    factors["vol_anom20"] = volume / volume.rolling(20).mean() - 1
    factors["volume_price_corr20"] = ret.rolling(20).corr(volume.pct_change(fill_method=None))
    factors["vol20"] = ret.rolling(20).std() * np.sqrt(252)
    factors["vol60"] = ret.rolling(60).std() * np.sqrt(252)
    factors["vol_change"] = factors["vol20"] - factors["vol60"]
    factors["risk_adj_mom20"] = factors["mom20"] / factors["vol20"].replace(0, np.nan)
    fwd = {}
    for h in HORIZONS:
        fwd[h] = close.shift(-h) / open_adj.shift(-1) - 1
        spy_h = spy.shift(-h) / spy.shift(-1) - 1
        fwd[h] = fwd[h].sub(spy_h, axis=0)
    mask = _membership_mask(base, close.index, close.columns)
    return factors, fwd, close, mask


def evaluate(factors: dict, fwd: dict, close: pd.DataFrame, mask: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = close.index
    cols = list(close.columns)
    M = mask.to_numpy(dtype=bool)
    rows, annual_rows, quint_rows = [], [], []
    for f in FACTORS:
        X = factors[f].to_numpy(dtype=float)
        for h in HORIZONS:
            Y = fwd[h].to_numpy(dtype=float)
            ics, rics, ls, top, turns, eval_dates = [], [], [], [], [], []
            prev_top = set()
            for i, d in enumerate(dates):
                m = M[i] & np.isfinite(X[i]) & np.isfinite(Y[i])
                if m.sum() < 30:
                    continue
                xv = X[i][m]; yv = Y[i][m]
                # Cross-sectional 1/99% winsorization; robust to bad price outliers.
                xv = np.clip(xv, np.nanquantile(xv, 0.01), np.nanquantile(xv, 0.99))
                yv = np.clip(yv, np.nanquantile(yv, 0.01), np.nanquantile(yv, 0.99))
                q = pd.qcut(xv, 5, labels=False, duplicates="drop")
                if len(np.unique(q)) < 5:
                    continue
                ics.append(np.corrcoef(xv, yv)[0, 1])
                rics.append(np.corrcoef(pd.Series(xv).rank(), pd.Series(yv).rank())[0, 1])
                eval_dates.append(d)
                qmeans = pd.Series(yv).groupby(q).mean()
                quint_rows.append({"factor": f, "horizon": h, "date": d, **{f"q{j+1}": float(qmeans.get(j, np.nan)) for j in range(5)}})
                ls.append(float(qmeans.get(4, np.nan) - qmeans.get(0, np.nan)))
                k = max(1, int(math.ceil(m.sum() * 0.10)))
                idx = np.argsort(-xv)[:k]
                top.append(float(np.mean(yv[idx])))
                names = set(np.array(cols)[m][idx])
                turns.append(1 - len(names & prev_top) / max(1, len(names)))
                prev_top = names
            if not ics:
                continue
            ic_s = pd.Series(ics, index=pd.to_datetime(eval_dates))
            cost = (np.nanmean(turns) if turns else np.nan) * COST_BPS / 10000
            t = hac_t(ic_s, 2 * h)
            rows.append({
                "factor": f, "horizon": h, "n_days": len(ic_s), "mean_ic": ic_s.mean(),
                "mean_rank_ic": np.mean(rics), "ic_hac_t": t, "ic_p": p_two_sided(t),
                "q5_minus_q1": np.mean(ls), "ls_hac_t": hac_t(pd.Series(ls), 2 * h),
                "top10_excess": np.mean(top), "top10_hac_t": hac_t(pd.Series(top), 2 * h),
                "avg_turnover": np.nanmean(turns), "cost_bps_est": cost * 10000,
                "net_ls": np.nanmean(ls) - cost, "net_top10": np.nanmean(top) - cost,
            })
            for period, (a, b) in PERIODS.items():
                mm = (ic_s.index >= a) & (ic_s.index <= b)
                annual_rows.append({"factor": f, "horizon": h, "period": period, "mean_ic": ic_s[mm].mean(), "mean_rank_ic": np.mean(np.array(rics)[mm]), "ls_mean": np.mean(np.array(ls)[mm]), "n_days": int(mm.sum())})
    res = pd.DataFrame(rows)
    res["bh_q"] = bh_q(res["ic_p"].tolist())
    # Average cross-sectional rank correlation, sampled to keep runtime bounded.
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
    factors, fwd, close, mask = build_factors(args.base)
    res, annual, quint, corr = evaluate(factors, fwd, close, mask)
    res.to_csv(args.out / "p11_2_factor_results.csv", index=False)
    annual.to_csv(args.out / "p11_2_annual_ic.csv", index=False)
    quint = quint.groupby(["factor", "horizon"], as_index=False)[["q1", "q2", "q3", "q4", "q5"]].mean()
    quint.to_csv(args.out / "p11_2_quintile_returns.csv", index=False)
    corr.to_csv(args.out / "p11_2_factor_correlation.csv")
    config = {"factors": FACTORS, "horizons": list(HORIZONS), "periods": PERIODS, "cost_bps_roundtrip": COST_BPS, "membership": "PIT snapshot expansion", "execution": "next adjusted open to adjusted close", "benchmark": "SPY close-to-close", "universe": "S&P 500 price panel / PIT filtered", "synthetic": False}
    (args.out / "p11_2_experiment_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    summary = {"rows": len(res), "factors": len(FACTORS), "horizons": len(HORIZONS), "universe_tickers": int(close.shape[1]), "status": "COMPUTED"}
    (args.out / "p11_2_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
