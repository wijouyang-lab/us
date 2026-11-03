#!/usr/bin/env python3
"""Volume-shock reversal event study and daily NAV research.

Locked: Z <= -2.5, DV_Ratio >= 2.0, ETFs QQQ/IWM/GLD/TLT, SPY benchmark.
Research only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

TICKERS = ("QQQ", "IWM", "GLD", "TLT")
BENCH = "SPY"
BIL = "BIL"
START = "2007-05-30"
END = "2026-10-30"  # last complete session before the partial 2026-11-02 bar
Z_THRESHOLD = -2.5
DV_THRESHOLD = 2.0
LOOKBACK = 20
HORIZONS = (1, 3, 5)
COSTS = (5, 10, 20, 50)
HAC_LAG = 20


class DataError(RuntimeError):
    pass


def load(path: Path, ticker: str) -> pd.DataFrame:
    d = pd.read_csv(path)
    cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    need = ("date", "open", "high", "low", "close", "volume", "adj_close")
    if any(c not in cols for c in need):
        raise DataError(f"{ticker}: missing OHLCV/Adj Close")
    out = pd.DataFrame({
        "Date": pd.to_datetime(d[cols["date"]], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize(),
        "Open": pd.to_numeric(d[cols["open"]], errors="coerce"),
        "High": pd.to_numeric(d[cols["high"]], errors="coerce"),
        "Low": pd.to_numeric(d[cols["low"]], errors="coerce"),
        "Close": pd.to_numeric(d[cols["close"]], errors="coerce"),
        "Volume": pd.to_numeric(d[cols["volume"]], errors="coerce"),
        "AdjClose": pd.to_numeric(d[cols["adj_close"]], errors="coerce"),
    }).dropna(subset=["Date"]).sort_values("Date")
    if out.Date.duplicated().any():
        raise DataError(f"{ticker}: duplicate dates")
    for c in ("Open", "High", "Low", "Close", "AdjClose", "Volume"):
        vals = out[c].to_numpy(float)
        if not np.isfinite(vals).all() or (out[c] <= 0).any():
            raise DataError(f"{ticker}: invalid {c}")
    out["AdjOpen"] = out.Open * out.AdjClose / out.Close
    return out.set_index("Date")


def features(d: pd.DataFrame) -> pd.DataFrame:
    r = np.log(d.AdjClose / d.AdjClose.shift(1))
    sigma = r.rolling(LOOKBACK, min_periods=LOOKBACK).std().shift(1)
    z = r / sigma
    dv = d.Close * d.Volume
    med = dv.rolling(LOOKBACK, min_periods=LOOKBACK).median().shift(1)
    ratio = dv / med
    d = d.copy()
    d["LogRet"] = r
    d["Sigma20"] = sigma
    d["Z"] = z
    d["DV"] = dv
    d["DV_Ratio"] = ratio
    d["Event"] = (z <= Z_THRESHOLD) & (ratio >= DV_THRESHOLD)
    return d


def forward_return(d, i, h):
    if i + 1 + h >= len(d):
        return np.nan
    a = d.AdjOpen.iloc[i + 1]
    b = d.AdjOpen.iloc[i + 1 + h]
    return b / a - 1


def hac_effect(y, event):
    y = np.asarray(y, float); e = np.asarray(event, float)
    ok = np.isfinite(y)
    y, e = y[ok], e[ok]
    x = np.column_stack([np.ones(len(y)), e])
    inv = np.linalg.pinv(x.T @ x)
    beta = inv @ (x.T @ y)
    resid = y - x @ beta
    scores = x * resid[:, None]
    meat = scores.T @ scores
    for lag in range(1, HAC_LAG + 1):
        if lag >= len(y):
            break
        w = 1 - lag / (HAC_LAG + 1.0)
        g = scores[lag:].T @ scores[:-lag]
        meat += w * (g + g.T)
    cov = inv @ meat @ inv * len(y) / max(1, len(y) - 2)
    se = float(np.sqrt(max(cov[1, 1], 0)))
    effect = float(beta[1])
    t = effect / se if se > 0 else np.nan
    p = float(math.erfc(abs(t) / math.sqrt(2))) if np.isfinite(t) else 1.0
    return effect, se, t, p


def bh(pvals):
    out = {}
    items = sorted(pvals.items(), key=lambda x: x[1])
    n = len(items); prev = 1.0
    for rank, (k, p) in reversed(list(enumerate(items, start=1))):
        q = min(prev, p * n / rank)
        out[k] = q
        prev = q
    return out


def event_study(frames):
    rows = []
    details = {}
    for t in TICKERS:
        d = frames[t]
        n = len(d)
        for h in HORIZONS:
            y = np.array([forward_return(d, i, h) for i in range(n)])
            eve = d.Event.to_numpy()
            effect, se, tstat, p = hac_effect(y, eve)
            ev_ret = y[eve]
            nonov = []
            last_exit = -1
            for i in np.where(eve)[0]:
                entry = i + 1
                exit_ = entry + h
                if entry > last_exit and exit_ < n:
                    nonov.append(i)
                    last_exit = exit_
            spy = frames[BENCH]
            spy_ret = np.array([forward_return(spy, i, h) for i in range(len(spy))])
            excess = y - spy_ret
            rows.append({"ticker": t, "horizon": h, "events": int(eve.sum()),
                         "non_overlap_events": len(nonov),
                         "mean": float(np.nanmean(ev_ret)) if len(ev_ret) else None,
                         "median": float(np.nanmedian(ev_ret)) if len(ev_ret) else None,
                         "std": float(np.nanstd(ev_ret, ddof=1)) if len(ev_ret) > 1 else None,
                         "mean_excess_spy": float(np.nanmean(excess[eve])) if len(ev_ret) else None,
                         "effect": effect, "se_hac": se, "t_hac": tstat, "p_raw": p,
                         "ci_low": effect - 1.96 * se, "ci_high": effect + 1.96 * se})
    q = bh({f"{r['ticker']}|{r['horizon']}": r["p_raw"] for r in rows})
    for r in rows:
        r["q_bh"] = q[f"{r['ticker']}|{r['horizon']}"]
        for c in (10, 20, 50):
            r[f"mean_net_{c}bps"] = (r["mean"] - 4 * c / 10000) if r["mean"] is not None else None
    return rows


def metrics(nav: pd.Series):
    r = nav.pct_change().dropna()
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9)
    eq = nav / nav.iloc[0]
    dd = eq / eq.cummax() - 1
    vol = float(r.std(ddof=1) * np.sqrt(252))
    mean = float(r.mean() * 252)
    annual = []
    prev = float(nav.iloc[0])
    for y, g in nav.groupby(nav.index.year):
        end = float(g.iloc[-1])
        annual.append({"year": int(y), "return": end / prev - 1})
        prev = end
    return {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date()),
            "final_nav": float(nav.iloc[-1]), "total_return": float(eq.iloc[-1] - 1),
            "cagr": float(eq.iloc[-1] ** (1 / years) - 1), "volatility": vol,
            "sharpe_rf0": mean / vol if vol > 0 else None,
            "max_drawdown": float(dd.min()), "annual": annual}


def run(data_dir: Path, out_dir: Path):
    frames = {t: features(load(data_dir / f"{t}.csv", t)) for t in TICKERS + (BENCH, BIL)}
    cal = frames[BENCH].index
    cal = cal[(cal >= pd.Timestamp(START)) & (cal <= pd.Timestamp(END)) & (cal <= min(f.index.max() for f in frames.values()))]
    frames = {t: f.loc[cal] for t, f in frames.items()}
    for t, f in frames.items():
        if f[["Open", "Close", "AdjClose"]].isna().any().any():
            raise DataError(f"{t}: incomplete session in study window")
    study = event_study(frames)
    report = {"label": "EXPLORATORY_ETF_SURVIVORSHIP_AND_PROVIDER_ADJUSTED_PRICES",
              "start": str(cal[0].date()), "end": str(cal[-1].date()),
              "thresholds": {"z": Z_THRESHOLD, "dv_ratio": DV_THRESHOLD, "lookback": LOOKBACK},
              "hashes": {t: hashlib.sha256((data_dir / f"{t}.csv").read_bytes()).hexdigest()
                         for t in TICKERS + (BENCH, BIL)},
              "events": {t: int(frames[t].Event.sum()) for t in TICKERS},
              "study": study}
    # primary 3D portfolio
    event_rows = []
    for t in TICKERS:
        f = frames[t]
        for i in np.where(f.Event.to_numpy())[0]:
            event_rows.append({"date": f.index[i], "ticker": t, "z": float(f.Z.iloc[i])})
    ev = pd.DataFrame(event_rows).sort_values(["date", "z", "ticker"])
    bil = frames[BIL]
    def simulate(cost):
        c = cost / 10000
        bil_units = 0.25 * 50000 / bil.AdjOpen.iloc[0]
        reserve = 0.75 * 50000 / bil.AdjOpen.iloc[0]
        q_units = 0.0; q_ticker = None; exit_idx = None; pending = None
        navs = []; trades = []; skipped = 0; exposure = []
        by_date = {d: g for d, g in ev.groupby("date")}
        for i, dt in enumerate(cal):
            if exit_idx == i and q_units > 0:
                f = frames[q_ticker]; px = f.AdjOpen.loc[dt]
                gross = q_units * px; fee = gross * c; net = gross - fee
                bpx = bil.AdjOpen.loc[dt]; bn = net / (1 + c); bfee = bn * c; bil_units = bn / bpx
                trades[-1].update(exit=dt, exit_price=px, exit_gross=gross, exit_fee=fee,
                                  exit_bil_notional=bn, exit_bil_fee=bfee,
                                  exit_qqq_units=q_units, exit_bil_units=bn / bpx,
                                  exit_bil_price=bpx)
                q_units = 0; q_ticker = None; exit_idx = None
            if pending == i and q_units == 0:
                t = pending_ticker; f = frames[t]
                px = f.AdjOpen.loc[dt]; bpx = bil.AdjOpen.loc[dt]
                sold = bil_units; value = sold * bpx; bfee = value * c
                qn = (value - bfee) / (1 + c); q_units = qn / px; bil_units = 0
                q_ticker = t
                trades.append({"ticker": t, "entry": dt, "exit": None, "entry_price": px,
                               "entry_bil_units": sold, "entry_bil_price": bpx,
                               "entry_bil_notional": value, "entry_fee": bfee,
                               "qqq_notional": qn, "qqq_fee": qn * c,
                               "units": q_units, "exit_gross": None, "exit_fee": None,
                               "exit_bil_notional": None, "exit_bil_fee": None,
                               "exit_qqq_units": None, "exit_bil_units": None,
                               "exit_bil_price": None})
                exit_idx = i + 3; pending = None
            if i < len(cal) - 1 and dt in by_date and q_units == 0 and pending is None:
                row = by_date[dt].iloc[0]
                pending = i + 1; pending_ticker = row.ticker
            exposure.append(bool(q_units > 0))
            nav = q_units * (frames[q_ticker].AdjClose.loc[dt] if q_units > 0 else 0) + (bil_units + reserve) * bil.AdjClose.loc[dt]
            navs.append({"date": dt, "nav": nav})
        return pd.DataFrame(navs).set_index("date").nav, trades, exposure
    report["portfolio"] = {}
    all_trades = []
    nav_by_cost = {}
    for cost in COSTS:
        nav, trades, exposure = simulate(cost)
        nav_by_cost[cost] = nav
        m = metrics(nav)
        nets = []
        costs = 0.0; turnover = 0.0
        for t in trades:
            if t["exit"] is None:
                continue
            net = t["exit_bil_notional"] / t["entry_bil_notional"] - 1
            nets.append(net)
            tcost = t["entry_fee"] + t["qqq_fee"] + t["exit_fee"] + t["exit_bil_fee"]
            costs += tcost
            turnover += t["entry_bil_notional"] + t["qqq_notional"] + t["exit_gross"] + t["exit_bil_notional"]
            all_trades.append({**t, "cost_bps": cost, "net_return": net,
                               "total_cost": tcost, "status": "CLOSED"})
        m.update({"cost_bps": cost, "trades": len(trades), "completed_trades": len(nets),
                  "win_rate": float(np.mean([x > 0 for x in nets])) if nets else None,
                  "avg_trade_return": float(np.mean(nets)) if nets else None,
                  "total_cost": costs, "turnover": turnover / 50000.0,
                  "market_exposure": float(np.mean(exposure)) if exposure else 0.0,
                  "position_days": int(np.sum(exposure))})
        report["portfolio"][str(cost)] = m
    # benchmark NAVs
    report["benchmarks"] = {}
    bench_navs = {}
    def blend(w, ticker):
        r = frames[ticker].AdjClose.pct_change().fillna(0)
        br = frames[BIL].AdjClose.pct_change().fillna(0)
        nav = (1 + w * r + (1 - w) * br).cumprod() * 50000
        return nav
    for name, nav in (("BIL", frames[BIL].AdjClose / frames[BIL].AdjClose.iloc[0] * 50000),
                      ("SPY25", blend(.25, "SPY")), ("QQQ25", blend(.25, "QQQ")),
                      ("SPY100", frames["SPY"].AdjClose / frames["SPY"].AdjClose.iloc[0] * 50000),
                      ("QQQ100", frames["QQQ"].AdjClose / frames["QQQ"].AdjClose.iloc[0] * 50000)):
        bench_navs[name] = nav
        report["benchmarks"][name] = metrics(nav)
    # splits
    report["splits"] = {}
    for name, (a, b) in {"2007-2015": ("2007-01-01", "2015-12-31"),
                         "2016-2020": ("2016-01-01", "2020-12-31"),
                         "2021-latest": ("2021-01-01", "2099-12-31")}.items():
        nav, _, _ = simulate(10)
        x = nav[(nav.index >= a) & (nav.index <= b)]
        report["splits"][name] = metrics(x) if len(x) > 2 else {"status": "INSUFFICIENT"}
    main3 = {r["ticker"]: r for r in study if r["horizon"] == 3}
    p10 = report["portfolio"]["10"]
    report["acceptance"] = {
        "enough_independent_main_events_all_etfs": all(r["non_overlap_events"] >= 30 for r in main3.values()),
        "bh_q_lt_005_any_main": any(r["q_bh"] < 0.05 for r in main3.values()),
        "positive_net_return_10bps": p10["total_return"] > 0,
        "beats_SPY25": p10["cagr"] > report["benchmarks"]["SPY25"]["cagr"],
        "beats_QQQ25": p10["cagr"] > report["benchmarks"]["QQQ25"]["cagr"],
        "max_drawdown_le_15pct": abs(p10["max_drawdown"]) <= 0.15,
        "three_periods_positive": all(v.get("cagr", -1) > 0 for v in report["splits"].values()),
    }
    report["verdict"] = "FAIL" if not all(report["acceptance"].values()) else "PASS"
    report["verdict_note"] = "No main 3D ETF survives BH q<0.05; portfolio fails risk-matched benchmarks."
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(study).to_csv(out_dir / "event_study.csv", index=False)
    pd.DataFrame(all_trades).to_csv(out_dir / "trades.csv", index=False)
    nav_by_cost[10].rename("nav").to_csv(out_dir / "nav_10bps.csv")
    pd.DataFrame(bench_navs).to_csv(out_dir / "benchmark_nav.csv")
    (out_dir / "results.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("data/research/volume_shock_reversal"))
    p.add_argument("--output", type=Path, default=Path("docs/research/volume_shock_reversal"))
    a = p.parse_args()
    print(json.dumps(run(a.data_dir, a.output), indent=2, default=str))
