#!/usr/bin/env python3
"""D. Yield-curve + financial-conditions monthly allocation.

Research only. Pre-registration: docs/research/MACRO_CURVE_D_PREREG.md.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

TICKERS = ("SPY", "IEF", "TLT", "BIL")
BASE_SLIP = 5.0
SLIPS = (1, 3, 5, 10, 20)
START_PIT = "2014-02-03"
START_EXPLORE = "2007-05-30"
END = "2026-10-30"


def load(t, path):
    d = pd.read_csv(path)
    cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    out = pd.DataFrame({
        "Date": pd.to_datetime(d[cols["date"]], utc=True).dt.tz_convert(None).dt.normalize(),
        "Open": pd.to_numeric(d[cols["open"]], errors="coerce"),
        "Close": pd.to_numeric(d[cols["close"]], errors="coerce"),
        "AdjClose": pd.to_numeric(d[cols["adj_close"]], errors="coerce"),
        "Dividends": pd.to_numeric(d[cols["dividends"]], errors="coerce").fillna(0.0),
    }).dropna().sort_values("Date")
    return out.set_index("Date")


def macro_series(path, col):
    d = pd.read_csv(path)
    dc = "observation_date" if "observation_date" in d.columns else "DATE"
    vc = col if col in d.columns else d.columns[1]
    d = d[[dc, vc]].rename(columns={dc: "date", vc: "value"})
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    return d.dropna().drop_duplicates("date").sort_values("date")


def pit_monthly(path, col):
    d = pd.read_csv(path)
    d["vintage_date"] = pd.to_datetime(d["vintage_date"])
    d["observation_date"] = pd.to_datetime(d["observation_date"])
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    return d.dropna().sort_values("vintage_date")


def target(curve, nfci):
    if pd.isna(curve) or pd.isna(nfci):
        return {"BIL": 1.0}
    inv = curve < 0
    tight = nfci > 0
    if inv and tight:
        return {"BIL": 1.0}
    if inv:
        return {"IEF": 0.40, "TLT": 0.30, "SPY": 0.15, "BIL": 0.15}
    if tight:
        return {"IEF": 0.30, "TLT": 0.20, "BIL": 0.50}
    return {"SPY": 0.70, "IEF": 0.15, "TLT": 0.15}


def commission(shares, notional, side):
    c = max(0.35, min(0.0035 * abs(shares), 0.01 * abs(notional)))
    sec = 0.0000278 * abs(notional) if side == "SELL" else 0.0
    taf = min(0.000166 * abs(shares), 8.30) if side == "SELL" else 0.0
    ex = 0.000003 * abs(shares)
    return c, sec, taf, ex


class Account:
    def __init__(self, frames, slip):
        self.f = frames; self.slip = slip
        self.cash = 50000.0; self.shares = {}; self.legs = []; self.navs = []
        self.turnover = 0.0; self.dividend_cash = 0.0

    def px(self, t, dt):
        return float(self.f[t].Open.loc[dt])

    def trade(self, dt, t, side, qty, px):
        qty = abs(float(qty)); notional = qty * px
        c, sec, taf, ex = commission(qty, notional, side)
        slip = notional * self.slip / 10000.0
        total = c + sec + taf + ex + slip
        if side == "BUY":
            self.cash -= notional + total; self.shares[t] = self.shares.get(t, 0.0) + qty
        else:
            self.cash += notional - total; self.shares[t] = self.shares.get(t, 0.0) - qty
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
    ann = []; prev = float(initial)
    for y, g in nav.groupby(nav.index.year):
        ann.append({"year": int(y), "return": float(g.iloc[-1]) / prev - 1}); prev = float(g.iloc[-1])
    return {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date()),
            "initial_equity": initial, "final_nav": float(nav.iloc[-1]),
            "total_return": float(eq.iloc[-1] - 1), "cagr": cagr, "volatility": vol,
            "sharpe_rf0": mean / vol if vol else None, "max_drawdown": mdd,
            "max_drawdown_peak_date": str(peak.date()), "max_drawdown_trough_date": str(trough.date()),
            "max_drawdown_recovery_date": str(rd.date()) if rd is not None else None,
            "max_drawdown_peak_to_trough_sessions": int(tp - pp),
            "max_drawdown_trough_to_recovery_sessions": int(rp - tp) if rp is not None else None,
            "longest_underwater_sessions": int(longest), "annual": ann}


def hac(y):
    y = np.asarray(y.dropna(), float)
    if len(y) < 30:
        return {"alpha": None, "p": None}
    beta = y.mean(); s = y - beta; meat = float(s @ s)
    for lag in range(1, 21):
        w = 1 - lag / 21.0; meat += 2 * w * float(s[lag:] @ s[:-lag])
    se = math.sqrt(max(meat / len(y) ** 2, 0))
    t = beta / se if se else None
    return {"alpha": beta * 252, "t": t, "p": math.erfc(abs(t) / math.sqrt(2)) if t is not None else None,
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


def month_ends(cal):
    return [d for i, d in enumerate(cal[:-1]) if cal[i + 1].month != d.month]


def total_return(frame, cal):
    c = frame.Close.loc[cal]; d = frame.Dividends.loc[cal]
    return ((c + d) / c.shift(1) - 1).fillna(0)


def run_case(frames, cal, curve_map, nfci_map, slip, label):
    acct = Account(frames, slip)
    bpx = acct.px("BIL", cal[0]); acct.trade(cal[0], "BIL", "BUY", int(50000 / bpx), bpx)
    me = set(month_ends(cal)); pending = None
    for i, dt in enumerate(cal):
        acct.credit_dividends(dt)
        if pending is not None:
            nav_open = acct.nav(dt, True); prices = {t: acct.px(t, dt) for t in TICKERS}
            desired = {t: int(max(0, nav_open * w) / prices[t]) for t, w in pending.items() if w > 0}
            deltas = {t: desired.get(t, 0) - acct.shares.get(t, 0.0) for t in set(list(acct.shares) + list(desired))}
            for t, d in deltas.items():
                if d < -1e-9:
                    acct.trade(dt, t, "SELL", -d, prices[t])
            for t, d in deltas.items():
                if d > 1e-9:
                    q = min(d, int(max(acct.cash, 0) / prices[t]))
                    if q > 0:
                        acct.trade(dt, t, "BUY", q, prices[t])
            pending = None
        acct.navs.append({"date": dt, "nav": acct.nav(dt)})
        if dt in me and i + 1 < len(cal):
            pending = target(curve_map.get(dt, np.nan), nfci_map.get(dt, np.nan))
    nav = pd.DataFrame(acct.navs).set_index("date")["nav"].astype(float)
    return nav, acct.legs


def align_pit(pit, month_ends_dates, col):
    # latest vintage on/before each month-end
    m = pd.DataFrame({"date": month_ends_dates})
    p = pit.rename(columns={"vintage_date": "date", "value": col})[["date", col]]
    x = pd.merge_asof(m.sort_values("date"), p.sort_values("date"), on="date", direction="backward")
    return dict(zip(x["date"], x[col]))


def run(data_dir: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    frames = {}
    for t in TICKERS:
        f = load(t, data_dir / f"{t}.csv"); frames[t] = f
    cal_all = frames["SPY"].index
    frames = {t: f.reindex(cal_all) for t, f in frames.items()}
    current_t = macro_series(data_dir / "T10Y3M.csv", "T10Y3M")
    current_n = macro_series(data_dir / "NFCI.csv", "NFCI")
    pit_t = pit_monthly(data_dir / "pit_T10Y3M.csv", "T10Y3M")
    pit_n = pit_monthly(data_dir / "pit_NFCI.csv", "NFCI")
    cases = {}
    for label, start in (("pit_2014_2026", START_PIT), ("exploratory_2007_2026", START_EXPLORE)):
        cal = cal_all[(cal_all >= pd.Timestamp(start)) & (cal_all <= pd.Timestamp(END))]
        mes = month_ends(cal)
        if label.startswith("pit"):
            cm = align_pit(pit_t, mes, "T10Y3M"); nm = align_pit(pit_n, mes, "NFCI")
        else:
            cm = {d: current_t[current_t.date <= d].iloc[-1].value for d in mes}
            nm = {d: current_n[current_n.date <= d].iloc[-1].value for d in mes}
        for slip in SLIPS:
            nav, legs = run_case(frames, cal, cm, nm, slip, label)
            key = f"{label}|{slip}"
            m = metrics(nav)
            m.update({"slip_bps": slip, "order_legs": len(legs),
                      "total_cost": sum(x["cost"] for x in legs)})
            if slip == BASE_SLIP:
                nav.rename("nav").to_csv(out / f"nav_{label}.csv")
                pd.DataFrame(legs).to_csv(out / f"trades_{label}.csv", index=False)
                m["bootstrap"] = bootstrap(nav)
                # stage-local
                m["stages"] = {}
                for name, (a, b) in {"2007-2013": ("2007-01-01", "2013-12-31"),
                                     "2014-2019": ("2014-01-01", "2019-12-31"),
                                     "2020-2026": ("2020-01-01", "2099-12-31")}.items():
                    x = nav[(nav.index >= a) & (nav.index <= b)]
                    m["stages"][name] = metrics(x, float(x.iloc[0])) if len(x) > 3 else {"status": "INSUFFICIENT"}
                r = nav.pct_change(fill_method=None).fillna(0)
                r.iloc[0] = nav.iloc[0] / 50000.0 - 1
                br = total_return(frames["BIL"], cal)
                sr = total_return(frames["SPY"], cal)
                m["hac_bil"] = hac(r - br); m["hac_spy"] = hac(r - sr)
            cases[key] = m
    return {"label": "D_MACRO_CURVE_FINANCIAL_CONDITIONS", "prereg": "docs/research/MACRO_CURVE_D_PREREG.md",
            "start_pit": START_PIT, "start_exploratory": START_EXPLORE, "end": END,
            "cost_model": {"commission_min": 0.35, "per_share": 0.0035, "base_slip_bps": BASE_SLIP},
            "cases": cases}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data/research/macro_d"))
    ap.add_argument("--out", type=Path, default=Path("docs/research/macro_d"))
    a = ap.parse_args()
    r = run(a.data_dir, a.out)
    (a.out / "results.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    print(json.dumps(r, indent=2, default=str)[:4000])
