#!/usr/bin/env python3
"""Low-frequency ETF strategy comparison.

Pre-registered candidates:
A. 12-month dual momentum, top 3, monthly, BIL fallback.
B. 200-day trend + inverse-vol, 10% vol target, monthly, BIL fallback.
C. Frozen QQQ TRANSITION 5-session reversal, 25% sleeve.

Costs: IBKR Pro Tiered commission + US sell fees + separate slippage.
Research only; no broker/order integration.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

TICKERS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC")
BIL = "BIL"
START = "2007-05-30"
END = "2026-10-30"
BASE_SLIP_BPS = 5.0
SLIP_GRID = (1, 3, 5, 10, 20)
HAC_LAG = 20


class DataError(RuntimeError):
    pass


def load(path, ticker):
    d = pd.read_csv(path)
    cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    need = ("date", "open", "high", "low", "close", "volume", "adj_close")
    if any(c not in cols for c in need):
        raise DataError(f"{ticker}: missing OHLCV")
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


def commission(shares, notional, side):
    shares = abs(float(shares)); notional = abs(float(notional))
    comm = max(0.35, min(0.0035 * shares, 0.01 * notional))
    sec = 0.0000278 * notional if side == "SELL" else 0.0
    taf = min(0.000166 * shares, 8.30) if side == "SELL" else 0.0
    exchange = 0.000003 * shares
    return comm, sec, taf, exchange


def leg_cost(shares, price, side, slip_bps):
    notional = abs(shares) * price
    comm, sec, taf, exch = commission(shares, notional, side)
    slip = notional * slip_bps / 10000.0
    return {"commission": comm, "sec_fee": sec, "taf_fee": taf,
            "exchange_fee": exch, "slippage": slip,
            "cost": comm + sec + taf + exch + slip}


def metrics(nav):
    r = nav.pct_change().dropna()
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9)
    eq = nav / nav.iloc[0]
    dd = eq / eq.cummax() - 1
    vol = float(r.std(ddof=1) * np.sqrt(252))
    mean = float(r.mean() * 252)
    downside = r[r < 0]
    sortino = mean / (float(downside.std(ddof=1) * np.sqrt(252))) if len(downside) > 1 else None
    mdd = float(dd.min())
    cagr = float(eq.iloc[-1] ** (1 / years) - 1)
    calmar = cagr / abs(mdd) if mdd < 0 else None
    # recovery: longest peak-to-recovery in sessions
    peak = eq.cummax(); under = eq < peak
    longest = cur = 0
    for u in under:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    annual = []; prev = float(nav.iloc[0])
    for y, g in nav.groupby(nav.index.year):
        annual.append({"year": int(y), "return": float(g.iloc[-1]) / prev - 1}); prev = float(g.iloc[-1])
    return {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date()),
            "final_nav": float(nav.iloc[-1]), "total_return": float(eq.iloc[-1] - 1),
            "cagr": cagr, "volatility": vol, "sharpe_rf0": mean / vol if vol else None,
            "sortino": sortino, "calmar": calmar, "max_drawdown": mdd,
            "max_drawdown_recovery_sessions": int(longest), "annual": annual}


def hac_alpha(excess):
    y = np.asarray(excess.dropna(), float)
    if len(y) < 30:
        return {"mean_annual": None, "t": None, "p": None, "ci_low": None, "ci_high": None, "n": len(y)}
    x = np.ones(len(y)); inv = 1.0 / (x.T @ x)
    beta = y.mean(); resid = y - beta; s = resid
    meat = float(s @ s)
    for lag in range(1, HAC_LAG + 1):
        if lag >= len(y):
            break
        w = 1 - lag / (HAC_LAG + 1.0)
        g = float(s[lag:] @ s[:-lag])
        meat += 2 * w * g
    se = math.sqrt(max(inv * meat * inv * len(y) / max(1, len(y) - 1), 0))
    t = beta / se if se else None
    p = math.erfc(abs(t) / math.sqrt(2)) if t is not None else None
    return {"mean_annual": beta * 252, "se_annual": se * 252, "t": t, "p": p,
            "ci_low": (beta - 1.96 * se) * 252, "ci_high": (beta + 1.96 * se) * 252, "n": len(y)}


def bh(pvals):
    items = sorted(pvals.items(), key=lambda x: x[1]); out = {}; prev = 1.0; n = len(items)
    for rank, (k, p) in reversed(list(enumerate(items, 1))):
        q = min(prev, p * n / rank); out[k] = q; prev = q
    return out


class Account:
    def __init__(self, frames, cal, slip_bps):
        self.f = frames; self.cal = cal; self.slip = slip_bps
        self.cash = 50000.0; self.shares = {}; self.legs = []; self.navs = []
        self.turnover = 0.0; self.risky_exposure = 0.0

    def px(self, t, dt):
        return float(self.f[t].AdjOpen.loc[dt])

    def trade(self, dt, ticker, side, shares, price):
        shares = abs(float(shares))
        if shares <= 0:
            return
        notional = shares * price
        c = leg_cost(shares, price, side, self.slip)
        if side == "BUY":
            self.cash -= notional + c["cost"]
            self.shares[ticker] = self.shares.get(ticker, 0.0) + shares
        else:
            self.cash += notional - c["cost"]
            self.shares[ticker] = self.shares.get(ticker, 0.0) - shares
        self.turnover += notional
        self.legs.append({"date": dt.date().isoformat(), "ticker": ticker, "side": side,
                          "shares": shares, "price": price, "notional": notional, **c})

    def nav(self, dt, open_=False):
        v = self.cash
        for t, sh in self.shares.items():
            p = float(self.f[t].AdjOpen.loc[dt] if open_ else self.f[t].AdjClose.loc[dt])
            v += sh * p
        return v

    def liquidate(self, dt):
        for t, sh in list(self.shares.items()):
            if sh > 1e-9:
                self.trade(dt, t, "SELL", sh, self.px(t, dt))


def month_end_dates(cal):
    out = set()
    for i, d in enumerate(cal[:-1]):
        if cal[i + 1].month != d.month:
            out.add(d)
    return out


def signal_A(frames, last):
    mom = {t: float(frames[t].AdjClose.loc[last] / frames[t].AdjClose.shift(252).loc[last] - 1)
           for t in TICKERS}
    bm = float(frames[BIL].AdjClose.loc[last] / frames[BIL].AdjClose.shift(252).loc[last] - 1)
    eligible = {t: v for t, v in mom.items() if np.isfinite(v) and v > bm}
    top = sorted(eligible.items(), key=lambda kv: kv[1], reverse=True)[:3]
    w = {t: 1.0 / 3.0 for t, _ in top}
    w[BIL] = max(0.0, 1.0 - sum(w.values()))
    return w


def signal_B(frames, last):
    rets = pd.DataFrame({t: frames[t].AdjClose.pct_change() for t in TICKERS})
    vol = rets.rolling(60, min_periods=60).std().loc[last] * np.sqrt(252)
    above = []
    for t in TICKERS:
        sma = frames[t].AdjClose.rolling(200, min_periods=200).mean().loc[last]
        if frames[t].AdjClose.loc[last] > sma and np.isfinite(vol[t]) and vol[t] > 0:
            above.append(t)
    if not above:
        return {BIL: 1.0}
    inv = np.array([1.0 / float(vol[t]) for t in above]); w = inv / inv.sum()
    cov = rets[above].rolling(60, min_periods=60).cov().loc[last] * 252
    est = float(np.sqrt(w @ cov.to_numpy() @ w))
    scale = min(1.0, 0.10 / est) if est > 0 else 0.0
    out = {t: float(wi * scale) for t, wi in zip(above, w)}
    out[BIL] = max(0.0, 1.0 - sum(out.values()))
    return out


def run_A_B(frames, cal, kind, slip):
    acct = Account(frames, cal, slip)
    # start in BIL
    bpx = acct.px(BIL, cal[0]); acct.trade(cal[0], BIL, "BUY", int(50000 / bpx), bpx)
    me = month_end_dates(cal); pending = None
    for i, dt in enumerate(cal):
        if pending is not None:
            target = pending; pending = None
            nav_open = acct.nav(dt, True)
            prices = {t: acct.px(t, dt) for t in set(list(acct.shares) + list(target))}
            desired = {}
            for t, w in target.items():
                desired[t] = int(max(0.0, nav_open * w) / prices[t]) if w > 0 else 0
            deltas = {t: desired.get(t, 0) - acct.shares.get(t, 0.0)
                      for t in set(list(acct.shares) + list(desired))}
            # sells first, then buys; no leverage
            for t, d in deltas.items():
                if d < -1e-9:
                    acct.trade(dt, t, "SELL", -d, prices[t])
            for t, d in deltas.items():
                if d > 1e-9:
                    px = prices[t]
                    qty = min(d, int(max(acct.cash, 0.0) / px))
                    if qty > 0:
                        acct.trade(dt, t, "BUY", qty, px)
            # residual cash remains; no leverage
        nav_close = acct.nav(dt)
        risky = sum(sh * float(frames[t].AdjClose.loc[dt]) for t, sh in acct.shares.items() if t != BIL)
        acct.navs.append({"date": dt, "nav": nav_close, "risky_value": risky})
        acct.risky_exposure += (risky / nav_close if nav_close > 0 else 0)
        if dt in me and i + 1 < len(cal):
            target = signal_A(frames, dt) if kind == "A" else signal_B(frames, dt)
            pending = target
    nav = pd.DataFrame(acct.navs).set_index("date")["nav"]
    return nav, acct.legs, acct.risky_exposure / len(cal), acct.turnover


def run_C(frames, cal, slip):
    q, b, s = frames["QQQ"], frames[BIL], frames["SPY"]
    q = q.copy()
    q["Ret5"] = q.AdjClose.pct_change(5, fill_method=None)
    q["Threshold"] = q.Ret5.rolling(252, min_periods=252).quantile(0.05).shift(1)
    s = s.copy()
    s["MA200"] = s.Close.rolling(200, min_periods=200).mean()
    s["Slope20"] = s.MA200 / s.MA200.shift(20) - 1
    s["Regime"] = np.select([(s.Close > s.MA200) & (s.Slope20 > 0),
                             (s.Close < s.MA200) & (s.Slope20 < 0)],
                            ["RISK_ON", "RISK_OFF"], default="TRANSITION")
    q["Signal"] = (q.Ret5 <= q.Threshold) & q.Threshold.notna() & s.Regime.eq("TRANSITION")
    acct = Account(frames, cal, slip)
    bpx = acct.px(BIL, cal[0]); total_bil = int(50000 / bpx)
    sleeve = int(total_bil * 0.25); reserve = total_bil - sleeve
    acct.shares[BIL] = float(sleeve); acct.cash -= sleeve * bpx
    # cash accounting: set cash 0 and reserve tracked as extra shares; easier: buy all BIL with cash
    acct.cash = 0.0
    acct.shares[BIL] = float(total_bil)
    q_units = 0.0; pending = None; exit_idx = None; entry_idx = None; sleeve_units = float(sleeve)
    for i, dt in enumerate(cal):
        if exit_idx == i and q_units > 0:
            px = float(q.AdjOpen.loc[dt])
            acct.trade(dt, "QQQ", "SELL", q_units, px)
            net = acct.cash
            bpx2 = acct.px(BIL, dt)
            qty = int(max(acct.cash, 0) / bpx2)
            acct.trade(dt, BIL, "BUY", qty, bpx2)
            q_units = 0; exit_idx = None
        if pending == i and q_units == 0:
            bpx2 = acct.px(BIL, dt)
            # sell 25% of current BIL position
            total_bil_sh = acct.shares.get(BIL, 0.0)
            sell = total_bil_sh * 0.25
            acct.trade(dt, BIL, "SELL", sell, bpx2)
            cash = max(acct.cash, 0)
            px = acct.px("QQQ", dt)
            q_units = int(cash / px)
            if q_units > 0:
                acct.trade(dt, "QQQ", "BUY", q_units, px)
            pending = None; exit_idx = i + 5
        nav_close = acct.nav(dt)
        risky = q_units * float(q.AdjClose.loc[dt])
        acct.navs.append({"date": dt, "nav": nav_close, "risky_value": risky})
        acct.risky_exposure += (risky / nav_close if nav_close > 0 else 0)
        if bool(q.Signal.loc[dt]) and q_units == 0 and pending is None and i + 1 < len(cal):
            pending = i + 1
    nav = pd.DataFrame(acct.navs).set_index("date")["nav"]
    return nav, acct.legs, acct.risky_exposure / len(cal), acct.turnover


def block_bootstrap_ci(nav, n=500, block=20):
    r = nav.pct_change().dropna().to_numpy()
    rng = np.random.default_rng(42)
    out = []
    for _ in range(n):
        idx = rng.integers(0, len(r), size=len(r))
        # circular block sample
        vals = []
        for s in idx:
            vals.extend(r[s:s + block])
            if len(vals) >= len(r):
                break
        vals = np.array(vals[:len(r)])
        out.append(np.prod(1 + vals) ** (252 / len(vals)) - 1)
    return {"cagr_ci_low": float(np.quantile(out, 0.025)),
            "cagr_ci_high": float(np.quantile(out, 0.975))}


def run(data_dir: Path, out_dir: Path):
    frames = {t: load(data_dir / f"{t}.csv", t) for t in TICKERS + (BIL,)}
    cal = frames["SPY"].index
    cal = cal[(cal >= pd.Timestamp(START)) & (cal <= pd.Timestamp(END))]
    frames = {t: f.loc[cal] for t, f in frames.items()}
    for t, f in frames.items():
        if f[["Open", "Close", "AdjClose"]].isna().any().any():
            raise DataError(f"{t}: incomplete session")
    results = {}; all_legs = []
    for kind in ("A", "B", "C"):
        for slip in SLIP_GRID:
            nav, legs, expo, turn = (run_A_B(frames, cal, kind, slip) if kind in ("A", "B")
                                     else run_C(frames, cal, slip))
            key = f"{kind}|{slip}"
            m = metrics(nav)
            m.update({"strategy": kind, "slip_bps": slip, "exposure": expo,
                      "turnover_annual": turn / (m["final_nav"] * max((cal[-1] - cal[0]).days / 365.25, 1e-9)),
                      "trades": len(legs), "total_cost": sum(x["cost"] for x in legs)})
            results[key] = m
            if slip == BASE_SLIP_BPS:
                for leg in legs:
                    all_legs.append({"strategy": kind, **leg})
            if slip == BASE_SLIP_BPS:
                nav.rename("nav").to_csv(out_dir / f"nav_{kind}.csv")
    # benchmarks
    bench = {}
    for t in ("BIL", "SPY"):
        nav = frames[t].AdjClose / frames[t].AdjClose.iloc[0] * 50000
        bench[t] = metrics(nav)
    # HAC alpha vs BIL and SPY, base cost
    tests = {}
    for kind in ("A", "B", "C"):
        nav = pd.read_csv(out_dir / f"nav_{kind}.csv", index_col=0, parse_dates=True)["nav"]
        r = nav.pct_change().fillna(0)
        br = frames[BIL].AdjClose.pct_change().fillna(0)
        sr = frames["SPY"].AdjClose.pct_change().fillna(0)
        tests[kind] = {"vs_BIL": hac_alpha(r - br), "vs_SPY": hac_alpha(r - sr)}
    qs = bh({k: v["vs_BIL"]["p"] for k, v in tests.items() if v["vs_BIL"]["p"] is not None})
    for k in tests:
        tests[k]["vs_BIL"]["q_bh"] = qs.get(k)
    # stages
    stages = {}
    for kind in ("A", "B", "C"):
        nav = pd.read_csv(out_dir / f"nav_{kind}.csv", index_col=0, parse_dates=True)["nav"]
        stages[kind] = {}
        for name, (a, b) in {"2007-2015": ("2007-01-01", "2015-12-31"),
                             "2016-2020": ("2016-01-01", "2020-12-31"),
                             "2021-2026": ("2021-01-01", "2099-12-31")}.items():
            x = nav[(nav.index >= a) & (nav.index <= b)]
            stages[kind][name] = metrics(x) if len(x) > 3 else {"status": "INSUFFICIENT"}
    for kind in ("A", "B", "C"):
        nav = pd.read_csv(out_dir / f"nav_{kind}.csv", index_col=0, parse_dates=True)["nav"]
        results[f"{kind}|5"]["bootstrap"] = block_bootstrap_ci(nav)
    report = {"label": "ETF_STRATEGY_RESEARCH_SIMULATED_COSTS",
              "start": str(cal[0].date()), "end": str(cal[-1].date()),
              "params": {"A": "12m momentum top3, monthly, BIL fallback",
                         "B": "200d SMA, inverse vol, 10% vol target, monthly, BIL fallback",
                         "C": "QQQ 5d reversal, q=0.05, 252d, SPY TRANSITION, 25% sleeve, 5 sessions"},
              "costs": {"model": "IBKR Pro Tiered + SEC/TAF/exchange + slippage",
                        "commission_min": 0.35, "commission_per_share": 0.0035,
                        "base_slip_bps_per_leg": BASE_SLIP_BPS,
                        "note": "Slippage is simulated, not historical quoted spread."},
              "results": results, "benchmarks": bench, "tests": tests, "stages": stages}
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_legs).to_csv(out_dir / "trades_base5.csv", index=False)
    (out_dir / "results.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("data/research/etf_strategy_study"))
    p.add_argument("--output", type=Path, default=Path("docs/research/etf_strategy_study"))
    a = p.parse_args()
    print(json.dumps(run(a.data_dir, a.output), indent=2, default=str))
