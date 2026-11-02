#!/usr/bin/env python3
"""QQQ TRANSITION web paper ledger (simulated historical replay).

No broker connectivity. All fills are SIMULATED. The historical replay is not a
prospective paper-observation clock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

INITIAL_CAPITAL = 50_000.0
SLEEVE = 0.25
COST_BPS = 10.0
HOLD = 5
LOOKBACK = 252
QUANTILE = 0.05
START = "2007-05-30"
LABEL = "SIMULATED_HISTORICAL_REPLAY"
STRATEGY_FINGERPRINT = "qqq-transition-reversal-v1|lookback=252|q=0.05|hold=5|sleeve=0.25|cost=10bps"


class DataError(RuntimeError):
    pass


def _load(path: Path, ticker: str) -> pd.DataFrame:
    d = pd.read_csv(path)
    cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    need = ("date", "open", "close", "adj_close")
    if any(c not in cols for c in need):
        raise DataError(f"{ticker}: missing OHLC/Adj Close")
    out = pd.DataFrame({
        "Date": pd.to_datetime(d[cols["date"]], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize(),
        "Open": pd.to_numeric(d[cols["open"]], errors="coerce"),
        "Close": pd.to_numeric(d[cols["close"]], errors="coerce"),
        "AdjClose": pd.to_numeric(d[cols["adj_close"]], errors="coerce"),
    }).dropna(subset=["Date"]).drop_duplicates("Date").sort_values("Date")
    for c in ("Open", "Close", "AdjClose"):
        if not np.isfinite(out[c].to_numpy(dtype=float)).all() or (out[c] <= 0).any():
            raise DataError(f"{ticker}: invalid {c}")
    out["AdjOpen"] = out.Open * out.AdjClose / out.Close
    return out.set_index("Date")


def build(qqq, bil, spy):
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
class Fill:
    date: str
    leg: str
    ticker: str
    side: str
    quantity: float
    reference_price: float
    fill_price: float
    notional: float
    cost: float
    status: str
    execution_mode: str
    trade_id: str


def run(data_dir: Path, out_dir: Path, dashboard_path: Path | None = None):
    q0 = _load(data_dir / "QQQ.csv", "QQQ")
    b0 = _load(data_dir / "BIL.csv", "BIL")
    s0 = _load(data_dir / "SPY.csv", "SPY")
    hashes = {name: hashlib.sha256((data_dir / f"{name}.csv").read_bytes()).hexdigest()
              for name in ("QQQ", "BIL", "SPY")}
    q0, b0, s0 = build(q0, b0, s0)
    cal = s0.index[(s0.index >= pd.Timestamp(START)) & (s0.index <= min(q0.index.max(), b0.index.max()))]
    q, b, s = q0.loc[cal], b0.loc[cal], s0.loc[cal]
    c = COST_BPS / 10000
    bil_units = SLEEVE * INITIAL_CAPITAL / float(b.AdjOpen.iloc[0])
    reserve_units = (1 - SLEEVE) * INITIAL_CAPITAL / float(b.AdjOpen.iloc[0])
    q_units = 0.0
    exit_idx = None
    pending = None
    fills: list[Fill] = []
    signals: list[dict] = []
    daily: list[dict] = []
    skipped = 0
    trade_no = 0
    active_signal_idx = None
    for i, dt in enumerate(cal):
        if exit_idx == i:
            qpx = float(q.AdjOpen.loc[dt]); gross = q_units * qpx; fee = gross * c; net = gross - fee
            fills.append(Fill(dt.date().isoformat(), "SELL_QQQ", "QQQ", "SELL", q_units, qpx, qpx, gross, fee,
                              "SIMULATED", "HISTORICAL_REPLAY", f"T{trade_no}"))
            bpx = float(b.AdjOpen.loc[dt]); bfee = net * c
            bil_units = (net - bfee) / bpx
            fills.append(Fill(dt.date().isoformat(), "BUY_BIL", "BIL", "BUY", net - bfee, bpx, bpx, net, bfee,
                              "SIMULATED", "HISTORICAL_REPLAY", f"T{trade_no}"))
            q_units = 0.0
            exit_idx = None
            if active_signal_idx is not None:
                signals[active_signal_idx].update({"exit_session": dt.date().isoformat(), "status": "CLOSED"})
                active_signal_idx = None
        if pending == i and q_units == 0:
            qpx = float(q.AdjOpen.loc[dt]); bpx = float(b.AdjOpen.loc[dt])
            value = bil_units * bpx; bil_units = 0.0
            bfee = value * c; qfee = (value - bfee) * c
            q_units = (value - bfee - qfee) / qpx
            trade_no += 1
            fills.append(Fill(dt.date().isoformat(), "SELL_BIL", "BIL", "SELL", value, bpx, bpx, value, bfee,
                              "SIMULATED", "HISTORICAL_REPLAY", f"T{trade_no}"))
            fills.append(Fill(dt.date().isoformat(), "BUY_QQQ", "QQQ", "BUY", value - bfee, qpx, qpx, value - bfee, qfee,
                              "SIMULATED", "HISTORICAL_REPLAY", f"T{trade_no}"))
            exit_idx = i + HOLD
            pending = None
            active_signal_idx = len(signals) - 1
            signals[active_signal_idx].update({"entry_session": dt.date().isoformat(), "status": "OPEN"})
        if bool(q.Signal.loc[dt]):
            signal = {"signal_date": dt.date().isoformat(), "ret5": float(q.Ret5.loc[dt]),
                      "threshold": float(q.Threshold.loc[dt]), "regime": str(s.Regime.loc[dt]),
                      "planned_entry": cal[i + 1].date().isoformat() if i + 1 < len(cal) else None,
                      "status": "SIGNAL"}
            if exit_idx is not None and exit_idx != i + 1:
                skipped += 1; signal["status"] = "SKIPPED_OVERLAP"
            elif pending is None:
                pending = i + 1
            signals.append(signal)
        qval = q_units * float(q.AdjClose.loc[dt])
        bval = (bil_units + reserve_units) * float(b.AdjClose.loc[dt])
        nav = qval + bval
        if i == 0:
            factor = INITIAL_CAPITAL / nav
            q_units *= factor; bil_units *= factor; reserve_units *= factor
            qval *= factor; bval *= factor; nav = INITIAL_CAPITAL
        daily.append({"date": dt.date().isoformat(), "nav": nav, "qqq_value": qval, "bil_value": bval,
                      "qqq_units": q_units, "bil_units": bil_units + reserve_units,
                      "weight": qval / nav if nav else 0.0,
                      "event": bool(q.Event.loc[dt]), "signal": bool(q.Signal.loc[dt]),
                      "regime": str(s.Regime.loc[dt])})
    daily_df = pd.DataFrame(daily)
    peak = daily_df.nav.cummax()
    dd = daily_df.nav / peak - 1
    max_dd = float(dd.min())
    last = daily_df.iloc[-1]
    current = signals[-1] if signals else None
    pending_entry = cal[pending].date().isoformat() if pending is not None and pending < len(cal) else None
    total_cost = sum(f.cost for f in fills)
    out_dir.mkdir(parents=True, exist_ok=True)
    daily_df.to_csv(out_dir / "daily_nav.csv", index=False)
    pd.DataFrame([asdict(f) for f in fills]).to_csv(out_dir / "fills.csv", index=False)
    pd.DataFrame(signals).to_csv(out_dir / "signals.csv", index=False)
    ledger = {
        "schema": "qqq-transition-web-paper-v1",
        "label": LABEL,
        "prospective_clock_started": False,
        "historical_replay": True,
        "initial_capital": INITIAL_CAPITAL,
        "sleeve_fraction": SLEEVE,
        "cost_bps_per_leg": COST_BPS,
        "strategy_fingerprint": STRATEGY_FINGERPRINT,
        "data_asof": cal[-1].date().isoformat(),
        "data_hashes": hashes,
        "engine_version": "qqq-paper-engine-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "account": {"cash": 0.0, "qqq_units": float(last.qqq_units), "bil_units": float(last.bil_units),
                    "nav": float(last.nav), "return_pct": float(last.nav / INITIAL_CAPITAL - 1),
                    "max_drawdown": max_dd, "weight": float(last.weight)},
        "counts": {"signals": len(signals), "skipped": skipped, "fills": len(fills),
                   "trades": len([f for f in fills if f.leg == "BUY_QQQ"])},
        "total_cost": total_cost,
        "pending_entry": pending_entry,
        "fills": [asdict(f) for f in fills],
        "signals": signals,
        "daily": daily,
    }
    (out_dir / "ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    latest_fills = [asdict(f) for f in fills[-4:]]
    recent_signals = signals[-5:]
    dashboard = {
        "label": LABEL, "prospective_clock_started": False, "historical_replay": True,
        "initial_capital": INITIAL_CAPITAL, "nav": float(last.nav),
        "return_pct": float(last.nav / INITIAL_CAPITAL - 1), "cash": 0.0,
        "qqq_units": float(last.qqq_units), "qqq_value": float(last.qqq_value),
        "bil_units": float(last.bil_units), "bil_value": float(last.bil_value),
        "weight": float(last.weight), "max_drawdown": max_dd, "total_cost": total_cost,
        "cost_bps_per_leg": COST_BPS, "data_asof": cal[-1].date().isoformat(),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "IN_POSITION" if q_units > 0 else ("PENDING_ENTRY" if pending_entry else "BIL"),
        "pending_entry": pending_entry,
        "trade": current, "recent_fills": latest_fills, "recent_signals": recent_signals,
        "counts": ledger["counts"], "strategy_fingerprint": STRATEGY_FINGERPRINT,
        "data_hashes": hashes, "engine_version": "qqq-paper-engine-v1",
        "nav_curve": [{"date": x["date"], "nav": x["nav"]} for x in daily[-260:]],
    }
    dash_path = Path(dashboard_path) if dashboard_path is not None else Path("dashboard/data/qqq_transition_paper.json")
    dash_path.parent.mkdir(parents=True, exist_ok=True)
    dash_path.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    return ledger, dashboard


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("data/research/qqq_transition_paper"))
    p.add_argument("--out-dir", type=Path, default=Path("qqq_transition_paper"))
    a = p.parse_args()
    ledger, dashboard = run(a.data_dir, a.out_dir)
    print(json.dumps({"nav": dashboard["nav"], "return_pct": dashboard["return_pct"],
                      "trades": dashboard["counts"]["trades"], "max_drawdown": dashboard["max_drawdown"]}))
