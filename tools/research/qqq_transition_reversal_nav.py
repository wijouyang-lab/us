#!/usr/bin/env python3
"""Independent daily-NAV backtest: QQQ 5-day reversal, SPY TRANSITION only."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

LOOKBACK = 252
QUANTILE = 0.05
HOLD = 5
COSTS = (5, 10, 20, 50)
WEIGHTS = (0.25, 0.50, 1.00)
START = "2007-05-30"
SPLITS = (("2007-2015", "2007-05-30", "2015-12-31"),
          ("2016-2020", "2016-01-01", "2020-12-31"),
          ("2021-latest", "2021-01-01", "2099-12-31"))
LABEL = "EXPLORATORY_ETF_SURVIVORSHIP_AND_PROVIDER_ADJUSTED_PRICES"


class MissingPriceError(RuntimeError):
    pass


def _finite(x) -> bool:
    return bool(np.isfinite(float(x)))


def load_prices(path: Path, ticker: str) -> pd.DataFrame:
    d = pd.read_csv(path)
    cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    missing = [c for c in ("date", "open", "close", "adj_close") if c not in cols]
    if missing:
        raise ValueError(f"{ticker}: missing {missing}")
    out = pd.DataFrame({
        "Date": pd.to_datetime(d[cols["date"]], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize(),
        "Open": pd.to_numeric(d[cols["open"]], errors="coerce"),
        "Close": pd.to_numeric(d[cols["close"]], errors="coerce"),
        "AdjClose": pd.to_numeric(d[cols["adj_close"]], errors="coerce"),
    }).dropna(subset=["Date"]).drop_duplicates("Date").sort_values("Date")
    for col in ("Open", "Close", "AdjClose"):
        bad = ~np.isfinite(out[col].to_numpy(dtype=float))
        if bad.any():
            dt = out.loc[bad, "Date"].iloc[0].date()
            raise ValueError(f"{ticker}: {col} NaN/Inf at {dt}")
        if (out[col] <= 0).any():
            dt = out.loc[out[col] <= 0, "Date"].iloc[0].date()
            raise ValueError(f"{ticker}: non-positive {col} at {dt}")
    out["AdjOpen"] = out.Open * out.AdjClose / out.Close
    return out.set_index("Date")


def build_panel(qqq, bil, spy):
    """SPY is the sole calendar. Features use all available warm-up history."""
    cal = spy.index
    q = qqq.reindex(cal)
    b = bil.reindex(cal)
    s = spy.copy()
    s["MA200"] = s.Close.rolling(200, min_periods=200).mean()
    s["Slope20"] = s.MA200 / s.MA200.shift(20) - 1
    s["Regime"] = np.select(
        [(s.Close > s.MA200) & (s.Slope20 > 0), (s.Close < s.MA200) & (s.Slope20 < 0)],
        ["RISK_ON", "RISK_OFF"], default="TRANSITION")
    q["Ret5"] = q.AdjClose.pct_change(5, fill_method=None)
    q["Threshold"] = q.Ret5.rolling(LOOKBACK, min_periods=LOOKBACK).quantile(QUANTILE).shift(1)
    q["Event"] = (q.Ret5 <= q.Threshold) & q.Threshold.notna()
    q["Signal"] = q.Event & s.Regime.eq("TRANSITION")
    return q, b, s


@dataclass
class Trade:
    entry: pd.Timestamp
    exit: pd.Timestamp | None
    entry_price: float
    exit_price: float | None
    units: float
    entry_notional: float
    exit_notional: float | None
    qqq_cost: float
    bil_cost: float
    gross_return: float | None
    net_return: float | None
    status: str


def simulate(q, b, s, weight: float, cost_bps: float, idle: str = "bil", cost_model: str = "all_legs"):
    cal = q.index
    c = cost_bps / 10000
    if not 0 < weight <= 1:
        raise ValueError("weight must be (0,1]")
    if cost_model not in ("qqq_only", "all_legs"):
        raise ValueError("bad cost model")
    bil_reserve_units = (1 - weight) / float(b.loc[cal[0], "AdjOpen"])
    bil_units = weight / float(b.loc[cal[0], "AdjOpen"]) if idle == "bil" else 0.0
    strat_cash = 0.0 if idle == "bil" else weight
    q_units = 0.0
    exit_idx = None
    pending = None
    trades: list[Trade] = []
    rows = []
    skipped = missing = 0
    for i, dt in enumerate(cal):
        if exit_idx == i:
            qpx = q.loc[dt, "AdjOpen"]
            if not _finite(qpx):
                raise MissingPriceError(f"QQQ exit open missing {dt.date()}")
            gross = q_units * float(qpx)
            qqq_fee = gross * c
            net = gross - qqq_fee
            q_units = 0.0
            bpx = b.loc[dt, "AdjOpen"]
            if not _finite(bpx):
                raise MissingPriceError(f"BIL exit open missing {dt.date()}")
            bil_fee = net * c if (cost_model == "all_legs" and idle == "bil") else 0.0
            if idle == "bil":
                bil_units = (net - bil_fee) / float(bpx)
            else:
                strat_cash = net
            t = trades[-1]
            t.exit, t.exit_price, t.exit_notional = dt, float(qpx), gross
            t.qqq_cost += qqq_fee; t.bil_cost += bil_fee
            t.gross_return = float(qpx) / t.entry_price - 1
            t.net_return = (net - bil_fee) / t.entry_notional - 1
            t.status = "CLOSED"
            exit_idx = None
        if pending == i and q_units == 0:
            qpx = q.loc[dt, "AdjOpen"]
            if not _finite(qpx):
                raise MissingPriceError(f"QQQ entry open missing {dt.date()}")
            bpx = b.loc[dt, "AdjOpen"]
            if not _finite(bpx):
                raise MissingPriceError(f"BIL entry open missing {dt.date()}")
            if idle == "bil":
                value = bil_units * float(bpx); bil_units = 0.0
            else:
                value = strat_cash; strat_cash = 0.0
            if value <= 0:
                raise MissingPriceError(f"non-positive strategy value {dt.date()}")
            bil_fee = value * c if (cost_model == "all_legs" and idle == "bil") else 0.0
            qqq_fee = (value - bil_fee) * c
            q_units = (value - bil_fee - qqq_fee) / float(qpx)
            trades.append(Trade(dt, None, float(qpx), None, q_units, value, None, qqq_fee, bil_fee, None, None, "OPEN"))
            exit_idx = i + HOLD
            pending = None
        if bool(q.loc[dt, "Signal"]):
            if exit_idx is not None and exit_idx != i + 1:
                skipped += 1
            elif pending is None:
                pending = i + 1
        if q_units > 0:
            if not _finite(q.loc[dt, "AdjClose"]):
                raise MissingPriceError(f"QQQ close mark missing {dt.date()}")
            strat_val = q_units * float(q.loc[dt, "AdjClose"])
        elif idle == "bil":
            if not _finite(b.loc[dt, "AdjClose"]):
                raise MissingPriceError(f"BIL close mark missing {dt.date()}")
            strat_val = bil_units * float(b.loc[dt, "AdjClose"])
        else:
            strat_val = strat_cash
        if not _finite(b.loc[dt, "AdjClose"]):
            raise MissingPriceError(f"BIL reserve close missing {dt.date()}")
        bil_val = bil_reserve_units * float(b.loc[dt, "AdjClose"])
        nav = strat_val + bil_val
        if i == 0:
            factor = 1.0 / nav
            q_units *= factor; bil_units *= factor; bil_reserve_units *= factor; strat_cash *= factor
            strat_val *= factor; bil_val *= factor; nav = 1.0
        rows.append({"date": dt, "nav": float(nav), "strategy_sleeve": float(strat_val),
                     "bil_sleeve": float(bil_val), "qqq_units": q_units,
                     "in_market": bool(q_units > 0), "regime": str(s.loc[dt, "Regime"]),
                     "event": bool(q.loc[dt, "Event"]), "signal": bool(q.loc[dt, "Signal"])})
    return pd.DataFrame(rows), trades, skipped, missing, int(q_units > 0), int(pending is not None)


def metrics(daily):
    s = daily.set_index("date").nav.astype(float)
    r = s.pct_change().dropna()
    years = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
    eq = s / s.iloc[0]
    dd = eq / eq.cummax() - 1
    vol = float(r.std(ddof=1) * np.sqrt(252)) if len(r) > 1 else None
    mean = float(r.mean() * 252) if len(r) else None
    downside = r[r < 0]
    dvol = float(downside.std(ddof=1) * np.sqrt(252)) if len(downside) > 1 else None
    return {"start": str(s.index[0].date()), "end": str(s.index[-1].date()), "days": len(s),
            "total_return": float(eq.iloc[-1] - 1), "cagr": float(eq.iloc[-1] ** (1 / years) - 1),
            "volatility": vol, "sharpe_rf0": float(mean / vol) if vol and vol > 0 else None,
            "sortino_rf0": float(mean / dvol) if dvol and dvol > 0 else None,
            "max_drawdown": float(dd.min()), "calmar": float((eq.iloc[-1] ** (1 / years) - 1) / abs(dd.min())) if dd.min() < 0 else None}


def annual(daily):
    d = daily.copy(); d["date"] = pd.to_datetime(d.date); d = d.set_index("date")
    out = []; prev = float(d.nav.iloc[0])
    for y, g in d.groupby(d.index.year):
        end = float(g.nav.iloc[-1]); out.append({"year": int(y), "return": float(end / prev - 1)}); prev = end
    return out


def buyhold(series):
    return pd.DataFrame({"date": series.index, "nav": series.values / series.iloc[0]})


def _summarize(trades, skipped, missing, opened, pending, daily, weight, cost, model):
    m = metrics(daily)
    qb = sum(t.entry_notional for t in trades)
    qs = sum((t.exit_notional or 0) for t in trades)
    qc = sum(t.qqq_cost for t in trades); bc = sum(t.bil_cost for t in trades)
    m.update({"weight": weight, "cost_bps": cost, "cost_model": model,
              "trades": len(trades), "completed_trades": sum(t.status == "CLOSED" for t in trades),
              "open_trades": opened, "pending_entries": pending,
              "skipped_overlap_signals": skipped, "missing_executions": missing,
              "market_exposure": float(daily.in_market.mean()),
              "qqq_buy_notional": qb, "qqq_sell_notional": qs,
              "bil_buy_notional": max(0.0, qb - qc), "bil_sell_notional": max(0.0, qs - qc),
              "qqq_cost": qc, "bil_cost": bc, "total_cost": qc + bc,
              "one_way_turnover": (qb + qs) / 2.0, "two_way_turnover": qb + qs,
              "avg_holding_days": float(np.mean([(t.exit - t.entry).days for t in trades if t.exit is not None])) if trades else 0.0,
              "annual": annual(daily)})
    return m


def run(qqq_csv, bil_csv, spy_csv, out_dir: Path):
    q = load_prices(qqq_csv, "QQQ"); b = load_prices(bil_csv, "BIL"); s = load_prices(spy_csv, "SPY")
    q, b, s = build_panel(q, b, s)
    cal = s.index[(s.index >= pd.Timestamp(START)) & (s.index <= min(q.index.max(), b.index.max()))]
    q, b, s = q.loc[cal], b.loc[cal], s.loc[cal]
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {"label": LABEL, "rules": {"lookback": LOOKBACK, "quantile": QUANTILE, "hold": HOLD},
               "start": str(cal[0].date()), "end": str(cal[-1].date()),
               "signals": int(q.Signal.sum()), "transition_days": int(s.Regime.eq("TRANSITION").sum()),
               "configs": {}, "benchmarks": {}, "hashes": {}}
    for p in (qqq_csv, bil_csv, spy_csv):
        results["hashes"][Path(p).name] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    for name, series in (("BIL", b.AdjClose), ("SPY", s.AdjClose), ("QQQ", q.AdjClose)):
        x = series.reindex(cal).dropna(); d = buyhold(x)
        results["benchmarks"][name] = {**metrics(d), "annual": annual(d)}
    all_daily, all_trades = [], []
    for weight in WEIGHTS:
        for cost in COSTS:
            for model in ("qqq_only", "all_legs"):
                daily, trades, skipped, missing, opened, pending = simulate(q, b, s, weight, cost, cost_model=model)
                key = f"w{int(weight*100)}_c{cost}_{model}"
                results["configs"][key] = _summarize(trades, skipped, missing, opened, pending, daily, weight, cost, model)
                d = daily.copy(); d["config"] = key; all_daily.append(d)
                for t in trades:
                    all_trades.append({"config": key, "entry": t.entry, "exit": t.exit,
                                       "entry_price": t.entry_price, "exit_price": t.exit_price,
                                       "units": t.units, "entry_notional": t.entry_notional,
                                       "exit_notional": t.exit_notional, "qqq_cost": t.qqq_cost,
                                       "bil_cost": t.bil_cost, "gross_return": t.gross_return,
                                       "net_return": t.net_return, "status": t.status})
    pd.concat(all_daily, ignore_index=True).to_csv(out_dir / "daily_nav.csv", index=False)
    pd.DataFrame(all_trades).to_csv(out_dir / "trade_ledger.csv", index=False)
    for cost in COSTS:
        for model in ("qqq_only", "all_legs"):
            daily, trades, skipped, missing, opened, pending = simulate(q, b, s, 1.0, cost, idle="cash", cost_model=model)
            results["configs"][f"strategy_only_c{cost}_{model}"] = _summarize(trades, skipped, missing, opened, pending, daily, 1.0, cost, model)
    for weight in WEIGHTS:
        daily, *_ = simulate(q, b, s, weight, 10, cost_model="all_legs")
        for name, a, bb in SPLITS:
            d = daily[(daily.date >= pd.Timestamp(a)) & (daily.date <= pd.Timestamp(bb))]
            results.setdefault("splits", {}).setdefault(f"w{int(weight*100)}", {})[name] = metrics(d) if len(d) > 2 else {"status": "INSUFFICIENT"}
    Path(out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--qqq", required=True); p.add_argument("--bil", required=True); p.add_argument("--spy", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(Path(a.qqq), Path(a.bil), Path(a.spy), Path(a.output))
