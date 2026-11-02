#!/usr/bin/env python3
"""Gap-confirmed continuation research (no production use).

Locked: Overnight_Z >= 1.0 AND Intraday_Z >= 0.5; 3-session primary hold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

TICKERS = ("SPY", "QQQ", "IWM", "GLD", "TLT")
BIL = "BIL"
START = "2007-05-30"
END = "2026-10-30"
LOOKBACK = 20
OZ_THRESHOLD = 1.0
IZ_THRESHOLD = 0.5
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
        if not np.isfinite(out[c].to_numpy(float)).all() or (out[c] <= 0).any():
            raise DataError(f"{ticker}: invalid {c}")
    out["AdjOpen"] = out.Open * out.AdjClose / out.Close
    return out.set_index("Date")


def features(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["Overnight"] = d.AdjOpen / d.AdjClose.shift(1) - 1
    d["Intraday"] = d.AdjClose / d.AdjOpen - 1
    d["SigmaOvernight"] = d.Overnight.rolling(LOOKBACK, min_periods=LOOKBACK).std().shift(1)
    d["SigmaIntraday"] = d.Intraday.rolling(LOOKBACK, min_periods=LOOKBACK).std().shift(1)
    d["OvernightZ"] = d.Overnight / d.SigmaOvernight
    d["IntradayZ"] = d.Intraday / d.SigmaIntraday
    d["Signal"] = (d.OvernightZ >= OZ_THRESHOLD) & (d.IntradayZ >= IZ_THRESHOLD)
    d["Score"] = d.OvernightZ + d.IntradayZ
    return d


def forward_return(d, i, h):
    if i + 1 + h >= len(d):
        return np.nan
    return d.AdjOpen.iloc[i + 1 + h] / d.AdjOpen.iloc[i + 1] - 1


def hac(y, event):
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
    eff = float(beta[1])
    t = eff / se if se > 0 else np.nan
    p = float(math.erfc(abs(t) / math.sqrt(2))) if np.isfinite(t) else 1.0
    return eff, se, t, p


def bh(pvals):
    items = sorted(pvals.items(), key=lambda x: x[1])
    out = {}; prev = 1.0; n = len(items)
    for rank, (k, p) in reversed(list(enumerate(items, 1))):
        q = min(prev, p * n / rank)
        out[k] = q; prev = q
    return out


def event_study(frames):
    rows = []
    for t in TICKERS:
        d = frames[t]; n = len(d); eve = d.Signal.to_numpy()
        spy_ret_by_h = {h: np.array([forward_return(frames["SPY"], i, h) for i in range(len(frames["SPY"]))]) for h in HORIZONS}
        for h in HORIZONS:
            y = np.array([forward_return(d, i, h) for i in range(n)])
            eff, se, ts, p = hac(y, eve)
            ev_ret = y[eve]
            non = []
            last_exit = -1
            for i in np.where(eve)[0]:
                ent = i + 1; ex = ent + h
                if ent > last_exit and ex < n:
                    non.append(i); last_exit = ex
            excess = y - spy_ret_by_h[h]
            rows.append({"ticker": t, "horizon": h, "events": int(eve.sum()),
                         "non_overlap_events": len(non),
                         "mean": float(np.nanmean(ev_ret)) if len(ev_ret) else None,
                         "median": float(np.nanmedian(ev_ret)) if len(ev_ret) else None,
                         "std": float(np.nanstd(ev_ret, ddof=1)) if len(ev_ret) > 1 else None,
                         "spy_mean": float(np.nanmean(spy_ret_by_h[h][eve])) if len(ev_ret) else None,
                         "mean_excess_spy": float(np.nanmean(excess[eve])) if len(ev_ret) else None,
                         "effect": eff, "se_hac": se, "t_hac": ts, "p_raw": p,
                         "ci_low": eff - 1.96 * se, "ci_high": eff + 1.96 * se})
    qs = bh({f"{r['ticker']}|{r['horizon']}": r["p_raw"] for r in rows})
    for r in rows:
        r["q_bh"] = qs[f"{r['ticker']}|{r['horizon']}"]
        r["mean_net_10bps"] = (r["mean"] - 0.004) if r["mean"] is not None else None
    return rows


def metrics(nav: pd.Series):
    r = nav.pct_change().dropna(); years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9)
    eq = nav / nav.iloc[0]; dd = eq / eq.cummax() - 1
    vol = float(r.std(ddof=1) * np.sqrt(252)); mean = float(r.mean() * 252)
    annual = []; prev = float(nav.iloc[0])
    for y, g in nav.groupby(nav.index.year):
        annual.append({"year": int(y), "return": float(g.iloc[-1]) / prev - 1}); prev = float(g.iloc[-1])
    return {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date()),
            "final_nav": float(nav.iloc[-1]), "total_return": float(eq.iloc[-1] - 1),
            "cagr": float(eq.iloc[-1] ** (1 / years) - 1), "volatility": vol,
            "sharpe_rf0": mean / vol if vol > 0 else None,
            "max_drawdown": float(dd.min()), "annual": annual}


def run(data_dir: Path, out_dir: Path):
    frames = {t: features(load(data_dir / f"{t}.csv", t)) for t in TICKERS + (BIL,)}
    cal = frames["SPY"].index
    cal = cal[(cal >= pd.Timestamp(START)) & (cal <= pd.Timestamp(END))]
    frames = {t: f.loc[cal] for t, f in frames.items()}
    for t, f in frames.items():
        if f[["Open", "Close", "AdjClose"]].isna().any().any():
            raise DataError(f"{t}: incomplete session")
    study = event_study(frames)
    hashes = {t: hashlib.sha256((data_dir / f"{t}.csv").read_bytes()).hexdigest() for t in TICKERS + (BIL,)}
    events = []
    for t in TICKERS:
        f = frames[t]
        for i in np.where(f.Signal.to_numpy())[0]:
            events.append({"date": f.index[i], "ticker": t, "oz": float(f.OvernightZ.iloc[i]),
                           "iz": float(f.IntradayZ.iloc[i]), "score": float(f.Score.iloc[i])})
    ev = pd.DataFrame(events).sort_values(["date", "score", "ticker"], ascending=[True, False, True])
    bil = frames[BIL]

    def simulate(cost):
        c = cost / 10000
        bil_units = 0.25 * 50000 / bil.AdjOpen.iloc[0]
        reserve = 0.75 * 50000 / bil.AdjOpen.iloc[0]
        q_units = 0.0; q_ticker = None; exit_idx = None; pending = None
        navs = []; trades = []; exposure = []; skipped = 0; by_date = {d: g for d, g in ev.groupby("date")}
        for i, dt in enumerate(cal):
            if exit_idx == i and q_units > 0:
                f = frames[q_ticker]; px = f.AdjOpen.loc[dt]
                gross = q_units * px; fee = gross * c; net = gross - fee
                bpx = bil.AdjOpen.loc[dt]; bn = net / (1 + c); bfee = bn * c; bil_units = bn / bpx
                trades[-1].update(exit=dt, exit_price=px, exit_gross=gross, exit_fee=fee,
                                  exit_bil_notional=bn, exit_bil_fee=bfee,
                                  exit_qqq_units=q_units, exit_bil_units=bn / bpx, exit_bil_price=bpx)
                q_units = 0; q_ticker = None; exit_idx = None
            if pending == i and q_units == 0:
                t = pending_ticker; f = frames[t]
                px = f.AdjOpen.loc[dt]; bpx = bil.AdjOpen.loc[dt]
                sold = bil_units; value = sold * bpx; bfee = value * c
                qn = (value - bfee) / (1 + c); q_units = qn / px; bil_units = 0; q_ticker = t
                trades.append({"ticker": t, "entry": dt, "exit": None, "entry_price": px,
                               "entry_bil_units": sold, "entry_bil_price": bpx,
                               "entry_bil_notional": value, "entry_fee": bfee,
                               "qqq_notional": qn, "qqq_fee": qn * c, "units": q_units,
                               "exit_gross": None, "exit_fee": None, "exit_bil_notional": None,
                               "exit_bil_fee": None, "exit_qqq_units": None,
                               "exit_bil_units": None, "exit_bil_price": None})
                exit_idx = i + 3; pending = None
            if i < len(cal) - 1 and dt in by_date and q_units == 0 and pending is None:
                pending = i + 1; pending_ticker = by_date[dt].iloc[0].ticker
            elif dt in by_date and (q_units > 0 or pending is not None):
                skipped += len(by_date[dt])
            exposure.append(bool(q_units > 0))
            nav = q_units * (frames[q_ticker].AdjClose.loc[dt] if q_units > 0 else 0) + (bil_units + reserve) * bil.AdjClose.loc[dt]
            navs.append({"date": dt, "nav": nav})
        return pd.DataFrame(navs).set_index("date").nav, trades, exposure, skipped

    report = {"label": "EXPLORATORY_ETF_SURVIVORSHIP_AND_PROVIDER_ADJUSTED_PRICES",
              "start": str(cal[0].date()), "end": str(cal[-1].date()),
              "thresholds": {"overnight_z": OZ_THRESHOLD, "intraday_z": IZ_THRESHOLD, "lookback": LOOKBACK},
              "hashes": hashes, "events": {t: int(frames[t].Signal.sum()) for t in TICKERS},
              "study": study}
    report["portfolio"] = {}; all_trades = []; nav_by_cost = {}
    for cost in COSTS:
        nav, trades, exposure, skipped = simulate(cost)
        nav_by_cost[cost] = nav
        nets = []; total_cost = 0.0; turnover = 0.0
        for t in trades:
            if t["exit"] is None:
                continue
            net = t["exit_bil_notional"] / t["entry_bil_notional"] - 1
            nets.append(net); tc = t["entry_fee"] + t["qqq_fee"] + t["exit_fee"] + t["exit_bil_fee"]
            total_cost += tc
            turnover += t["entry_bil_notional"] + t["qqq_notional"] + t["exit_gross"] + t["exit_bil_notional"]
            all_trades.append({**t, "cost_bps": cost, "net_return": net, "total_cost": tc, "status": "CLOSED"})
        m = metrics(nav)
        m.update({"cost_bps": cost, "trades": len(trades), "completed_trades": len(nets),
                  "win_rate": float(np.mean([x > 0 for x in nets])) if nets else None,
                  "avg_trade_return": float(np.mean(nets)) if nets else None,
                  "total_cost": total_cost, "turnover": turnover / 50000,
                  "market_exposure": float(np.mean(exposure)),
                  "position_days": int(np.sum(exposure)), "skipped_signals": skipped})
        report["portfolio"][str(cost)] = m
    report["benchmarks"] = {}
    bench_navs = {}
    def blend(w, t):
        return (1 + w * frames[t].AdjClose.pct_change().fillna(0) +
                (1 - w) * frames[BIL].AdjClose.pct_change().fillna(0)).cumprod() * 50000
    for name, nav in (("BIL", frames[BIL].AdjClose / frames[BIL].AdjClose.iloc[0] * 50000),
                      ("SPY25", blend(.25, "SPY")), ("QQQ25", blend(.25, "QQQ")),
                      ("SPY100", frames["SPY"].AdjClose / frames["SPY"].AdjClose.iloc[0] * 50000),
                      ("QQQ100", frames["QQQ"].AdjClose / frames["QQQ"].AdjClose.iloc[0] * 50000)):
        bench_navs[name] = nav; report["benchmarks"][name] = metrics(nav)
    report["splits"] = {}
    for name, (a, b) in {"2007-2015": ("2007-01-01", "2015-12-31"),
                         "2016-2020": ("2016-01-01", "2020-12-31"),
                         "2021-latest": ("2021-01-01", "2099-12-31")}.items():
        nav = nav_by_cost[10]; x = nav[(nav.index >= a) & (nav.index <= b)]
        report["splits"][name] = metrics(x) if len(x) > 2 else {"status": "INSUFFICIENT"}
    # diagnostics
    p10 = report["portfolio"]["10"]
    tr = [t for t in all_trades if t["cost_bps"] == 10]
    pnl = [(t["exit_bil_notional"] - t["entry_bil_notional"]) for t in tr if t["exit_bil_notional"]]
    top3 = sum(sorted(pnl, reverse=True)[:3]) if pnl else 0
    contrib = {}
    for t in tr:
        contrib[t["ticker"]] = contrib.get(t["ticker"], 0.0) + (t["exit_bil_notional"] - t["entry_bil_notional"])
    spy_ma = frames["SPY"].AdjClose.rolling(200, min_periods=200).mean()
    regimes = {"above_200d": 0, "below_200d": 0, "warming_up": 0}
    for _, e in ev.iterrows():
        ma = spy_ma.loc[e["date"]]
        if pd.isna(ma):
            regimes["warming_up"] += 1
        elif frames["SPY"].AdjClose.loc[e["date"]] >= ma:
            regimes["above_200d"] += 1
        else:
            regimes["below_200d"] += 1
    consecutive = 0
    for t in TICKERS:
        ds = list(frames[t].index[frames[t].Signal])
        pos = {d: i for i, d in enumerate(frames[t].index)}
        consecutive += sum(1 for a, b in zip(ds, ds[1:]) if pos[b] - pos[a] <= 3)
    zs = np.concatenate([frames[t].OvernightZ.dropna().to_numpy() for t in TICKERS])
    report["diagnostics"] = {
        "overnight_z_quantiles": {str(q): float(np.quantile(zs, q)) for q in (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)},
        "intraday_z_quantiles": {str(q): float(np.quantile(np.concatenate([frames[t].IntradayZ.dropna().to_numpy() for t in TICKERS]), q)) for q in (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)},
        "signals_by_etf": report["events"],
        "signals_by_market_regime": regimes,
        "consecutive_signals_within_3_sessions": consecutive,
        "skipped_signals": p10["skipped_signals"],
        "per_etf_pnl": contrib,
        "max_single_trade_pnl": float(max(pnl)) if pnl else None,
        "top3_pnl_sum": float(top3),
        "final_nav_ex_top3": float(p10["final_nav"] - top3),
    }
    report["acceptance"] = {
        "enough_independent_all": all(r["non_overlap_events"] >= 30 for r in study if r["horizon"] == 3),
        "bh_q_lt_005_any": any(r["q_bh"] < 0.05 for r in study if r["horizon"] == 3),
        "positive_net_10bps": p10["cagr"] > 0,
        "beats_SPY25": p10["cagr"] > report["benchmarks"]["SPY25"]["cagr"],
        "beats_QQQ25": p10["cagr"] > report["benchmarks"]["QQQ25"]["cagr"],
        "maxdd_le_15": abs(p10["max_drawdown"]) <= 0.15,
        "splits_all_positive": all(v.get("cagr", -1) > 0 for v in report["splits"].values()),
        "not_top3_dependent": (p10["final_nav"] - top3) > 50000,
    }
    report["verdict"] = "PASS" if all(report["acceptance"].values()) else "FAIL"
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
    p.add_argument("--output", type=Path, default=Path("docs/research/gap_confirmed_continuation"))
    a = p.parse_args()
    print(json.dumps(run(a.data_dir, a.output), indent=2, default=str))
