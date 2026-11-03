#!/usr/bin/env python3
"""G. Fixed 20% QQQ / 80% BIL risk budget. Research only."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd
from tools.research.ibkr_costs import fees, range_fees

TICKERS = ("QQQ", "BIL")
START = "2007-05-30"
END = "2026-10-30"
BASE_SLIP = 5.0
SLIPS = (1, 3, 5, 10, 20)
W = {"QQQ": 0.20, "BIL": 0.80}


def load(t, path):
    d = pd.read_csv(path); cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    out = pd.DataFrame({
        "Date": pd.to_datetime(d[cols["date"]], utc=True).dt.tz_convert(None).dt.normalize(),
        "Open": pd.to_numeric(d[cols["open"]], errors="coerce"),
        "Close": pd.to_numeric(d[cols["close"]], errors="coerce"),
        "Dividends": pd.to_numeric(d[cols["dividends"]], errors="coerce").fillna(0.0),
    }).dropna().sort_values("Date")
    return out.set_index("Date")


class Account:
    def __init__(self, frames, slip):
        self.f = frames; self.slip = slip; self.cash = 50000.0
        self.shares = {}; self.legs = []; self.navs = []; self.dividend_cash = 0.0; self.turnover = 0.0

    def px(self, t, dt): return float(self.f[t].Open.loc[dt])

    def trade(self, dt, t, side, qty, px):
        qty = abs(float(qty)); notional = qty * px
        f = fees(qty, px, side, dt); slip = notional * self.slip / 10000.0
        total = f["cost"] + slip
        if side == "BUY":
            self.cash -= notional + total; self.shares[t] = self.shares.get(t, 0) + qty
        else:
            self.cash += notional - total; self.shares[t] = self.shares.get(t, 0) - qty
        self.turnover += notional
        self.legs.append({"date": dt.date().isoformat(), "ticker": t, "side": side, "shares": qty,
                          "price": px, "notional": notional, **f, "slippage": slip, "total_cost": total})

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


def benchmark(frames, t, cal):
    shares = 50000.0 / float(frames[t].Open.loc[cal[0]]); cash = 0.0; vals = []
    for dt in cal:
        div = float(frames[t].Dividends.loc[dt])
        if div > 0: cash += shares * div
        vals.append(shares * float(frames[t].Close.loc[dt]) + cash)
    return pd.Series(vals, index=cal)


def run(data_dir: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    frames = {t: load(t, data_dir / f"{t}.csv") for t in TICKERS}
    cal_all = frames["BIL"].index
    frames = {t: f.reindex(cal_all) for t, f in frames.items()}
    cal = cal_all[(cal_all >= pd.Timestamp(START)) & (cal_all <= pd.Timestamp(END))]
    for t in TICKERS:
        if frames[t].loc[cal, ["Open", "Close"]].isna().any().any():
            raise ValueError(f"{t}: missing portfolio price")
    me = {cal[i] for i in range(len(cal) - 1) if cal[i + 1].month != cal[i].month}
    results = {}
    for slip in SLIPS:
        a = Account(frames, slip)
        nav0 = 50000.0
        for t, w in W.items():
            px = a.px(t, cal[0]); q = int(nav0 * w / px)
            if q > 0: a.trade(cal[0], t, "BUY", q, px)
        pending = False
        for i, dt in enumerate(cal):
            a.credit_dividends(dt)
            if pending:
                nav_open = a.nav(dt, True); prices = {t: a.px(t, dt) for t in TICKERS}
                desired = {t: int(nav_open * w / prices[t]) for t, w in W.items()}
                deltas = {t: desired[t] - a.shares.get(t, 0) for t in TICKERS}
                for t, d in deltas.items():
                    if d < 0: a.trade(dt, t, "SELL", -d, prices[t])
                for t, d in deltas.items():
                    if d > 0:
                        q = min(d, int(max(a.cash, 0) / prices[t]))
                        if q > 0: a.trade(dt, t, "BUY", q, prices[t])
                pending = False
            nv = a.nav(dt)
            risky = a.shares.get("QQQ", 0) * float(frames["QQQ"].Close.loc[dt])
            a.navs.append({"date": dt, "nav": nv, "risky": risky})
            if dt in me and i + 1 < len(cal): pending = True
        df = pd.DataFrame(a.navs).set_index("date")
        nav = df["nav"].astype(float); m = metrics(nav)
        m.update({"slip_bps": slip, "order_legs": len(a.legs),
                  "total_cost": sum(x["total_cost"] for x in a.legs),
                  "commission": sum(x["commission"] for x in a.legs),
                  "sec_fee": sum(x["sec_fee"] for x in a.legs),
                  "taf_fee": sum(x["taf_fee"] for x in a.legs),
                  "cat_fee": sum(x["cat_fee"] for x in a.legs),
                  "clearing_fee": sum(x["clearing_fee"] for x in a.legs),
                  "exchange_fee": sum(x["exchange_fee"] for x in a.legs),
                  "slippage": sum(x["slippage"] for x in a.legs),
                  "dividend_cash": a.dividend_cash,
                  "exposure": float((df["risky"] / df["nav"]).mean())})
        if slip == BASE_SLIP:
            nav.rename("nav").to_csv(out / "nav_G.csv")
            pd.DataFrame(a.legs).to_csv(out / "trades_G.csv", index=False)
            m["bootstrap"] = bootstrap(nav)
            m["stages"] = {}
            for name, (x0, x1) in {"2007-2015": ("2007-01-01", "2015-12-31"),
                                   "2016-2020": ("2016-01-01", "2020-12-31"),
                                   "2021-2026": ("2021-01-01", "2099-12-31")}.items():
                x = nav[(nav.index >= x0) & (nav.index <= x1)]
                m["stages"][name] = metrics(x, float(x.iloc[0])) if len(x) > 3 else {"status": "INSUFFICIENT"}
            r = nav.pct_change(fill_method=None).fillna(0); r.iloc[0] = nav.iloc[0] / 50000.0 - 1
            br = benchmark(frames, "BIL", cal); qr = benchmark(frames, "QQQ", cal)
            m["hac_bil"] = hac(r - br.pct_change(fill_method=None).fillna(0))
            m["hac_qqq"] = hac(r - qr.pct_change(fill_method=None).fillna(0))
            m["benchmark_BIL"] = metrics(br, 50000.0)
            m["benchmark_QQQ"] = metrics(qr, 50000.0)
        results[f"G|{slip}"] = m
    return {"label": "G_FIXED_RISK_BUDGET_QQQ_BIL", "status": "EXPLORATORY_IMPLEMENTATION_VALIDATION",
            "start": START, "end": END, "weights": W,
            "cost_model": {"source": "IBKR Pro Tiered calibrated 2026 public schedule",
                           "sec_rate": 0.0000206, "cat_per_share": 0.000003,
                           "clearing_per_share": 0.00020, "exchange_assumption": 0.00010,
                           "base_slip_bps": BASE_SLIP},
            "results": results}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", type=Path, default=Path("data/research/fixed_risk_budget"))
    ap.add_argument("--out", type=Path, default=Path("docs/research/fixed_risk_budget"))
    a = ap.parse_args(); r = run(a.data_dir, a.out)
    (a.out / "results.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    print(json.dumps(r, indent=2, default=str)[:3000])
