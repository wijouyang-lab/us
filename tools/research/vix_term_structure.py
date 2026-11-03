#!/usr/bin/env python3
"""F. VIX/VXV backwardation risk filter. Research only."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

TICKERS = ("SPY", "IEF", "TLT", "BIL")
START_PIT = "2014-01-02"
START_EXPLORE = "2007-12-04"
END = "2026-10-30"
BASE_SLIP = 5.0
SLIPS = (1, 3, 5, 10, 20)


def load(t, path):
    d = pd.read_csv(path); cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    out = pd.DataFrame({
        "Date": pd.to_datetime(d[cols["date"]], utc=True).dt.tz_convert(None).dt.normalize(),
        "Open": pd.to_numeric(d[cols["open"]], errors="coerce"),
        "Close": pd.to_numeric(d[cols["close"]], errors="coerce"),
        "Dividends": pd.to_numeric(d[cols["dividends"]], errors="coerce").fillna(0.0),
    }).dropna().sort_values("Date")
    return out.set_index("Date")


def macro(path, col):
    d = pd.read_csv(path); dc = "observation_date" if "observation_date" in d.columns else "DATE"
    d = d[[dc, col]].rename(columns={dc: "date", col: "value"})
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    return d.dropna().sort_values("date")


def allocation(vix, vxv):
    if vix is None or vxv is None or pd.isna(vix) or pd.isna(vxv):
        return {"BIL": 1.0}
    if vix > vxv:
        return {"BIL": 1.0}
    return {"SPY": 0.70, "IEF": 0.15, "TLT": 0.15}


def commission(shares, notional, side):
    c = max(0.35, min(0.0035 * abs(shares), 0.01 * abs(notional)))
    sec = 0.0000278 * abs(notional) if side == "SELL" else 0.0
    taf = min(0.000166 * abs(shares), 8.30) if side == "SELL" else 0.0
    return c, sec, taf, 0.000003 * abs(shares)


class Account:
    def __init__(self, frames, slip):
        self.f = frames; self.slip = slip; self.cash = 50000.0
        self.shares = {}; self.legs = []; self.navs = []; self.turnover = 0.0; self.dividend_cash = 0.0

    def px(self, t, dt): return float(self.f[t].Open.loc[dt])

    def trade(self, dt, t, side, qty, px):
        qty = abs(float(qty)); notional = qty * px
        c, sec, taf, ex = commission(qty, notional, side)
        slip = notional * self.slip / 10000.0; total = c + sec + taf + ex + slip
        if side == "BUY":
            self.cash -= notional + total; self.shares[t] = self.shares.get(t, 0) + qty
        else:
            self.cash += notional - total; self.shares[t] = self.shares.get(t, 0) - qty
        self.turnover += notional
        self.legs.append({"date": dt.date().isoformat(), "ticker": t, "side": side, "shares": qty,
                          "price": px, "notional": notional, "commission": c, "sec_fee": sec,
                          "taf_fee": taf, "exchange_fee": ex, "slippage": slip, "cost": total})

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
    return {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date()), "initial_equity": initial,
            "final_nav": float(nav.iloc[-1]), "total_return": float(eq.iloc[-1] - 1), "cagr": cagr,
            "volatility": vol, "sharpe_rf0": mean / vol if vol else None, "max_drawdown": mdd,
            "max_drawdown_peak_date": str(peak.date()), "max_drawdown_trough_date": str(trough.date()),
            "max_drawdown_recovery_date": str(rd.date()) if rd is not None else None,
            "max_drawdown_peak_to_trough_sessions": int(tp - pp),
            "max_drawdown_trough_to_recovery_sessions": int(rp - tp) if rp is not None else None,
            "longest_underwater_sessions": int(longest), "annual": annual}


def hac(y):
    y = np.asarray(y.dropna(), float)
    if len(y) < 30: return {"alpha": None, "p": None}
    beta = y.mean(); s = y - beta; meat = float(s @ s)
    for lag in range(1, 21):
        meat += 2 * (1 - lag / 21.0) * float(s[lag:] @ s[:-lag])
    se = math.sqrt(max(meat / len(y) ** 2, 0)); t = beta / se if se else None
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


def total_return(frame, cal):
    c = frame.Close.loc[cal]; d = frame.Dividends.loc[cal]
    return ((c + d) / c.shift(1) - 1).fillna(0)


def run_case(frames, cal, signals, slip):
    acct = Account(frames, slip)
    acct.trade(cal[0], "BIL", "BUY", int(50000 / acct.px("BIL", cal[0])), acct.px("BIL", cal[0]))
    me = {d for i, d in enumerate(cal[:-1]) if cal[i + 1].month != d.month}
    pending = None; events = []; durations = []
    for i, dt in enumerate(cal):
        acct.credit_dividends(dt)
        if pending is not None:
            nav_open = acct.nav(dt, True); prices = {t: acct.px(t, dt) for t in TICKERS}
            desired = {t: int(max(0, nav_open * w) / prices[t]) for t, w in pending.items() if w > 0}
            deltas = {t: desired.get(t, 0) - acct.shares.get(t, 0) for t in set(list(acct.shares) + list(desired))}
            for t, d in deltas.items():
                if d < -1e-9: acct.trade(dt, t, "SELL", -d, prices[t])
            for t, d in deltas.items():
                if d > 1e-9:
                    q = min(d, int(max(acct.cash, 0) / prices[t]))
                    if q > 0: acct.trade(dt, t, "BUY", q, prices[t])
            pending = None
        nv = acct.nav(dt)
        risky = sum(sh * float(frames[t].Close.loc[dt]) for t, sh in acct.shares.items() if t != "BIL")
        acct.navs.append({"date": dt, "nav": nv, "risky": risky})
        if dt in me and i + 1 < len(cal):
            vix, vxv = signals.get(dt, (None, None))
            pending = allocation(vix, vxv)
            if vix is not None and vxv is not None:
                events.append({"date": str(dt.date()), "vix": vix, "vxv": vxv,
                               "state": "BACKWARDATION" if vix > vxv else "NORMAL"})
    df = pd.DataFrame(acct.navs).set_index("date")
    return df["nav"].astype(float), acct.legs, events, float((df["risky"] / df["nav"]).mean())


def run(data_dir: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    frames = {t: load(t, data_dir / f"{t}.csv") for t in TICKERS}
    all_cal = frames["SPY"].index; frames = {t: f.reindex(all_cal) for t, f in frames.items()}
    vix = macro(data_dir / "VIXCLS.csv", "VIXCLS"); vxv = macro(data_dir / "VXVCLS.csv", "VXVCLS")
    pit = pd.read_csv(data_dir / "pit_vix_vxv.csv")
    pit_sig = {pd.Timestamp(r.decision_date): (float(r.vix), float(r.vxv)) for r in pit.itertuples()
               if pd.notna(r.vix) and pd.notna(r.vxv)}
    results = {}
    for label, start in (("pit_2014_2026", START_PIT), ("exploratory_2007_2026", START_EXPLORE)):
        cal = all_cal[(all_cal >= pd.Timestamp(start)) & (all_cal <= pd.Timestamp(END))]
        if label.startswith("pit"):
            sig = {d: pit_sig[d] for d in cal if d in pit_sig}
        else:
            sig = {}
            for d in cal:
                prior = d - pd.Timedelta(days=1)
                a = vix[vix.date <= prior]; b = vxv[vxv.date <= prior]
                if len(a) and len(b):
                    sig[d] = (float(a.iloc[-1].value), float(b.iloc[-1].value))
        me_set = {cal[i] for i in range(len(cal) - 1) if cal[i + 1].month != cal[i].month}
        for slip in SLIPS:
            nav, legs, events, expo = run_case(frames, cal, sig, slip)
            m = metrics(nav); m.update({"slip_bps": slip, "order_legs": len(legs),
                                        "total_cost": sum(x["cost"] for x in legs),
                                        "exposure": expo,
                                        "backwardation_days": sum(1 for e in events if e["state"] == "BACKWARDATION"),
                                        "missing_decisions": sum(1 for d in me_set if d not in sig)})
            if slip == BASE_SLIP:
                nav.rename("nav").to_csv(out / f"nav_{label}.csv")
                pd.DataFrame(legs).to_csv(out / f"trades_{label}.csv", index=False)
                pd.DataFrame(events).to_csv(out / f"events_{label}.csv", index=False)
                m["bootstrap"] = bootstrap(nav)
                m["stages"] = {}
                for name, (a, b) in {"2007-2015": ("2007-01-01", "2015-12-31"),
                                     "2016-2020": ("2016-01-01", "2020-12-31"),
                                     "2021-2026": ("2021-01-01", "2099-12-31")}.items():
                    x = nav[(nav.index >= a) & (nav.index <= b)]
                    m["stages"][name] = metrics(x, float(x.iloc[0])) if len(x) > 3 else {"status": "INSUFFICIENT"}
                r = nav.pct_change(fill_method=None).fillna(0); r.iloc[0] = nav.iloc[0] / 50000.0 - 1
                m["hac_bil"] = hac(r - total_return(frames["BIL"], cal))
                m["hac_spy"] = hac(r - total_return(frames["SPY"], cal))
            results[f"{label}|{slip}"] = m
    return {"label": "F_VIX_VXV_BACKWARDATION_FILTER", "start_pit": START_PIT,
            "start_exploratory": START_EXPLORE, "end": END,
            "rules": {"backwardation": {"BIL": 1.0}, "normal": {"SPY": 0.70, "IEF": 0.15, "TLT": 0.15}},
            "cost_model": {"commission_min": 0.35, "per_share": 0.0035, "base_slip_bps": BASE_SLIP},
            "results": results}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", type=Path, default=Path("data/research/vix_term_structure"))
    ap.add_argument("--out", type=Path, default=Path("docs/research/vix_term_structure"))
    a = ap.parse_args(); r = run(a.data_dir, a.out)
    (a.out / "results.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    print(json.dumps(r, indent=2, default=str)[:3000])
