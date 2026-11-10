#!/usr/bin/env python3
"""E. 10Y real-yield 63-session shock filter.

Research only. Pre-registration: docs/research/REAL_YIELD_E_PREREG.md.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

TICKERS = ("SPY", "IEF", "TLT", "BIL")
START = "2007-05-30"
END = "2026-10-30"
BASE_SLIP = 5.0
SLIPS = (1, 3, 5, 10, 20)


def load(t, path):
    d = pd.read_csv(path)
    cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    out = pd.DataFrame({
        "Date": pd.to_datetime(d[cols["date"]], utc=True).dt.tz_convert(None).dt.normalize(),
        "Open": pd.to_numeric(d[cols["open"]], errors="coerce"),
        "Close": pd.to_numeric(d[cols["close"]], errors="coerce"),
        "Dividends": pd.to_numeric(d[cols["dividends"]], errors="coerce").fillna(0.0),
    }).dropna().sort_values("Date")
    return out.set_index("Date")


def commission(shares, notional, side):
    c = max(0.35, min(0.0035 * abs(shares), 0.01 * abs(notional)))
    sec = 0.0000278 * abs(notional) if side == "SELL" else 0.0
    taf = min(0.000166 * abs(shares), 8.30) if side == "SELL" else 0.0
    ex = 0.000003 * abs(shares)
    return c, sec, taf, ex


class Account:
    def __init__(self, frames, slip):
        self.f = frames; self.slip = slip; self.cash = 50000.0
        self.shares = {}; self.legs = []; self.navs = []; self.turnover = 0.0
        self.dividend_cash = 0.0

    def px(self, t, dt):
        return float(self.f[t].Open.loc[dt])

    def trade(self, dt, t, side, qty, px):
        qty = abs(float(qty)); notional = qty * px
        c, sec, taf, ex = commission(qty, notional, side)
        slip = notional * self.slip / 10000.0
        total = c + sec + taf + ex + slip
        if side == "BUY":
            self.cash -= notional + total; self.shares[t] = self.shares.get(t, 0) + qty
        else:
            self.cash += notional - total; self.shares[t] = self.shares.get(t, 0) - qty
        self.turnover += notional
        self.legs.append({"date": dt.date().isoformat(), "ticker": t, "side": side,
                          "shares": qty, "price": px, "notional": notional,
                          "commission": c, "sec_fee": sec, "taf_fee": taf,
                          "exchange_fee": ex, "slippage": slip, "cost": total})

    def credit_dividends(self, dt):
        for t, sh in self.shares.items():
            if sh > 0 and dt in self.f[t].index:
                div = float(self.f[t].Dividends.loc[dt])
                if div > 0:
                    self.cash += sh * div; self.dividend_cash += sh * div

    def nav(self, dt, open_=False):
        return self.cash + sum(sh * float(self.f[t].Open.loc[dt] if open_ else self.f[t].Close.loc[dt])
                               for t, sh in self.shares.items())


def metrics(nav, initial=50000.0):
    r = nav.pct_change(fill_method=None); r.iloc[0] = nav.iloc[0] / initial - 1; r = r.dropna()
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9)
    eq = nav / initial; cum = eq.cummax(); dd = eq / cum - 1
    vol = float(r.std(ddof=1) * np.sqrt(252)); mean = float(r.mean() * 252)
    mdd = float(dd.min()); cagr = float(eq.iloc[-1] ** (1 / years) - 1)
    trough = dd.idxmin(); tp = nav.index.get_loc(trough)
    peak = eq.iloc[:tp + 1].idxmax(); pp = nav.index.get_loc(peak)
    after = eq.iloc[tp:]; rec = after[after >= eq.loc[peak]]
    rd = rec.index[0] if len(rec) else None
    rp = nav.index.get_loc(rd) if rd is not None else None
    under = (eq < cum).to_numpy(); longest = cur = 0
    for u in under:
        cur = cur + 1 if u else 0; longest = max(longest, cur)
    annual = []; prev = float(initial)
    for y, g in nav.groupby(nav.index.year):
        annual.append({"year": int(y), "return": float(g.iloc[-1]) / prev - 1}); prev = float(g.iloc[-1])
    return {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date()),
            "initial_equity": initial, "final_nav": float(nav.iloc[-1]),
            "total_return": float(eq.iloc[-1] - 1), "cagr": cagr, "volatility": vol,
            "sharpe_rf0": mean / vol if vol else None, "max_drawdown": mdd,
            "max_drawdown_peak_date": str(peak.date()), "max_drawdown_trough_date": str(trough.date()),
            "max_drawdown_recovery_date": str(rd.date()) if rd is not None else None,
            "max_drawdown_peak_to_trough_sessions": int(tp - pp),
            "max_drawdown_trough_to_recovery_sessions": int(rp - tp) if rp is not None else None,
            "longest_underwater_sessions": int(longest), "annual": annual}


def hac(y):
    y = np.asarray(y.dropna(), float)
    if len(y) < 30:
        return {"alpha": None, "p": None}
    beta = y.mean(); s = y - beta; meat = float(s @ s)
    for lag in range(1, 21):
        meat += 2 * (1 - lag / 21.0) * float(s[lag:] @ s[:-lag])
    se = math.sqrt(max(meat / len(y) ** 2, 0))
    t = beta / se if se else None
    return {"alpha": beta * 252, "t": t, "p": math.erfc(abs(t) / math.sqrt(2)) if t else None,
            "ci_low": (beta - 1.96 * se) * 252, "ci_high": (beta + 1.96 * se) * 252, "n": len(y)}


def bootstrap(nav, initial=50000.0, n=500, block=20, seed=42):
    r = nav.pct_change(fill_method=None); r.iloc[0] = nav.iloc[0] / initial - 1; r = r.dropna().to_numpy()
    rng = np.random.default_rng(seed); out = []
    for _ in range(n):
        starts = rng.integers(0, len(r), size=int(np.ceil(len(r) / block)))
        idx = np.concatenate([(np.arange(s, s + block) % len(r)) for s in starts])[:len(r)]
        out.append(np.prod(1 + r[idx]) ** (252 / len(idx)) - 1)
    return {"method": "circular_block_bootstrap", "seed": seed, "block_sessions": block,
            "samples": n, "low": float(np.quantile(out, .025)), "high": float(np.quantile(out, .975))}


def allocation(change):
    if change is None or pd.isna(change) or change >= 0.50:
        return {"BIL": 1.0}
    return {"SPY": 0.70, "IEF": 0.15, "TLT": 0.15}


def total_return(frame, cal):
    shares = 50000.0 / float(frame.Open.loc[cal[0]])
    cash = 0.0; vals = []
    for dt in cal:
        div = float(frame.Dividends.loc[dt])
        if div > 0: cash += shares * div
        vals.append(shares * float(frame.Close.loc[dt]) + cash)
    nav = pd.Series(vals, index=cal); r = nav / 50000.0
    out = r.pct_change(fill_method=None); out.iloc[0] = r.iloc[0] - 1
    return out


def signal_map(pit):
    return {pd.Timestamp(r.decision_date): float(r.change_63) for r in pit.itertuples()
            if pd.notna(r.change_63) and pd.Timestamp(r.decision_date) <= pd.Timestamp(END)}


def run_case(frames, cal, smap, slip):
    acct = Account(frames, slip)
    acct.trade(cal[0], "BIL", "BUY", int(50000 / acct.px("BIL", cal[0])), acct.px("BIL", cal[0]))
    me = {d for i, d in enumerate(cal[:-1]) if cal[i + 1].month != d.month}
    pending = None; triggers = []
    for i, dt in enumerate(cal):
        acct.credit_dividends(dt)
        if pending is not None:
            nav_open = acct.nav(dt, True); prices = {t: acct.px(t, dt) for t in TICKERS}
            desired = {t: int(max(0, nav_open * w) / prices[t]) for t, w in pending.items() if w > 0}
            deltas = {t: desired.get(t, 0) - acct.shares.get(t, 0) for t in set(list(acct.shares) + list(desired))}
            for t, d in deltas.items():
                if d < -1e-9:
                    acct.trade(dt, t, "SELL", -d, prices[t])
            for t, d in deltas.items():
                if d > 1e-9:
                    q = min(d, int(max(acct.cash, 0) / prices[t]))
                    if q > 0:
                        acct.trade(dt, t, "BUY", q, prices[t])
            pending = None
        nv = acct.nav(dt)
        risky = sum(sh * float(frames[t].Close.loc[dt]) for t, sh in acct.shares.items() if t != "BIL")
        acct.navs.append({"date": dt, "nav": nv, "risky": risky})
        if dt in me and i + 1 < len(cal):
            ch = smap.get(dt)
            if ch is not None and ch >= 0.50:
                triggers.append({"date": str(dt.date()), "change_63": ch, "state": "TRIGGER"})
            elif ch is None:
                triggers.append({"date": str(dt.date()), "change_63": None, "state": "MISSING"})
            pending = allocation(ch)
    df = pd.DataFrame(acct.navs).set_index("date")
    expo = float((df["risky"] / df["nav"]).mean())
    return df["nav"].astype(float), acct.legs, triggers, expo


def run(data_dir: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    frames = {t: load(t, data_dir / f"{t}.csv") for t in TICKERS}
    all_cal = frames["SPY"].index
    frames = {t: f.reindex(all_cal) for t, f in frames.items()}
    cal = all_cal[(all_cal >= pd.Timestamp(START)) & (all_cal <= pd.Timestamp(END))]
    for t, f in frames.items():
        if f.loc[cal, ["Open", "Close"]].isna().any().any():
            raise ValueError(f"{t}: missing portfolio price")
    pit = pd.read_csv(data_dir / "pit_DFII10.csv")
    smap = signal_map(pit)
    results = {}
    for slip in SLIPS:
        nav, legs, triggers, expo = run_case(frames, cal, smap, slip)
        m = metrics(nav); m.update({"slip_bps": slip, "order_legs": len(legs),
                                    "total_cost": sum(x["cost"] for x in legs),
                                    "triggers": sum(1 for x in triggers if x["state"] == "TRIGGER"),
                                    "missing_signals": sum(1 for x in triggers if x["state"] == "MISSING"),
                                    "exposure": expo})
        if slip == BASE_SLIP:
            nav.rename("nav").to_csv(out / "nav_E.csv")
            pd.DataFrame(legs).to_csv(out / "trades_E.csv", index=False)
            pd.DataFrame(triggers).to_csv(out / "triggers_E.csv", index=False)
            m["bootstrap"] = bootstrap(nav)
            m["stages"] = {}
            for name, (a, b) in {"2007-2015": ("2007-01-01", "2015-12-31"),
                                 "2016-2020": ("2016-01-01", "2020-12-31"),
                                 "2021-2026": ("2021-01-01", "2099-12-31")}.items():
                x = nav[(nav.index >= a) & (nav.index <= b)]
                m["stages"][name] = metrics(x, float(x.iloc[0])) if len(x) > 3 else {"status": "INSUFFICIENT"}
            r = nav.pct_change(fill_method=None).fillna(0)
            r.iloc[0] = nav.iloc[0] / 50000.0 - 1
            br = total_return(frames["BIL"], cal)
            sr = total_return(frames["SPY"], cal)
            m["hac_bil"] = hac(r - br); m["hac_spy"] = hac(r - sr)
        results[f"E|{slip}"] = m
    # exposure: fraction of NAV in risky legs
    # recompute from nav/trades is approximate; use shares not retained. Mark from trade intent.
    return {"label": "E_REAL_YIELD_SHOCK_FILTER", "start": START, "end": END,
            "rules": {"lookback_sessions": 63, "threshold_pp": 0.50,
                      "trigger": {"BIL": 1.0}, "normal": {"SPY": 0.70, "IEF": 0.15, "TLT": 0.15}},
            "cost_model": {"commission_min": 0.35, "per_share": 0.0035, "base_slip_bps": BASE_SLIP},
            "results": results}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", type=Path, default=Path("data/research/real_yield_shock"))
    ap.add_argument("--out", type=Path, default=Path("docs/research/real_yield_shock"))
    a = ap.parse_args()
    r = run(a.data_dir, a.out)
    (a.out / "results.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    print(json.dumps(r, indent=2, default=str)[:3000])
