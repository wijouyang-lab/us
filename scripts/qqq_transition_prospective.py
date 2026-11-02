#!/usr/bin/env python3
"""Prospective QQQ TRANSITION simulated account (no broker, no orders).

Default state is NOT_STARTED. The start command is explicit and is not run here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.qqq_transition_paper import (
    COST_BPS, HOLD, INITIAL_CAPITAL, SLEEVE, STRATEGY_FINGERPRINT,
    _load, build,
)

DEFAULT_STATE = {
    "schema": "qqq-transition-prospective-v1",
    "status": "NOT_STARTED",
    "prospective_clock_started": False,
    "start_date": None,
    "initial_capital": INITIAL_CAPITAL,
    "sleeve_fraction": SLEEVE,
    "cost_bps_per_leg": COST_BPS,
    "strategy_fingerprint": STRATEGY_FINGERPRINT,
    "positions": {"cash": 0.0, "qqq_units": 0.0, "bil_units": 0.0, "reserve_units": 0.0},
    "nav": INITIAL_CAPITAL,
    "observation_days": 0,
    "signals": 0,
    "skipped": 0,
    "fills": [],
    "signal_rows": [],
    "observations": [],
    "pending_entry": None,
    "exit_date": None,
    "data_hashes": {},
    "code_sha": None,
    "generated_at_utc": None,
}


def _state_path(out_dir: Path) -> Path:
    return out_dir / "state.json"


def ensure(out_dir: Path, dashboard_path: Path | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = _state_path(out_dir)
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_STATE, indent=2), encoding="utf-8")
        _write_dashboard(out_dir, DEFAULT_STATE, dashboard_path)
    return json.loads(p.read_text(encoding="utf-8"))


def _hashes(data_dir: Path) -> dict:
    return {t: hashlib.sha256((data_dir / f"{t}.csv").read_bytes()).hexdigest() for t in ("QQQ", "BIL", "SPY")}


def _write_dashboard(out_dir: Path, state: dict, dashboard_path: Path | None = None) -> None:
    d = Path(dashboard_path) if dashboard_path is not None else Path("dashboard/data/qqq_transition_paper_prospective.json")
    d.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "PROSPECTIVE_SIMULATION", "status": state["status"],
        "prospective_clock_started": state["prospective_clock_started"],
        "start_date": state["start_date"], "initial_capital": state["initial_capital"],
        "nav": state["nav"], "return_pct": state["nav"] / state["initial_capital"] - 1 if state["initial_capital"] else 0,
        "cash": state["positions"]["cash"], "qqq_units": state["positions"]["qqq_units"],
        "bil_units": state["positions"]["bil_units"] + state["positions"]["reserve_units"],
        "observation_days": state["observation_days"], "signals": state["signals"],
        "skipped": state["skipped"], "max_drawdown": _max_dd(state),
        "total_cost": sum(x.get("cost", 0) for x in state["fills"]),
        "last_data_date": state.get("last_data_date"), "recent_fills": state["fills"][-4:],
        "recent_signals": state["signal_rows"][-5:],
        "code_sha": state.get("code_sha"), "data_hashes": state.get("data_hashes", {}),
        "updated_at_utc": state.get("generated_at_utc"),
    }
    d.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _max_dd(state) -> float:
    navs = [x["nav"] for x in state.get("observations", [])]
    if not navs:
        return 0.0
    s = pd.Series(navs, dtype=float)
    return float((s / s.cummax() - 1).min())


def start(data_dir: Path, out_dir: Path, start_date: str, code_sha: str, dashboard_path: Path | None = None):
    state = ensure(out_dir, dashboard_path)
    if state["status"] != "NOT_STARTED":
        raise RuntimeError("prospective account already started")
    q = _load(data_dir / "QQQ.csv", "QQQ"); b = _load(data_dir / "BIL.csv", "BIL"); s = _load(data_dir / "SPY.csv", "SPY")
    q, b, s = build(q, b, s)
    start = pd.Timestamp(start_date)
    if start not in s.index:
        raise RuntimeError("start_date is not a SPY session")
    if not (s.index < start).any():
        raise RuntimeError("no history before start")
    bpx = float(b.loc[start, "AdjOpen"])
    state.update({
        "status": "RUNNING", "prospective_clock_started": True, "start_date": start.date().isoformat(),
        "positions": {"cash": 0.0, "qqq_units": 0.0,
                      "bil_units": SLEEVE * INITIAL_CAPITAL / bpx,
                      "reserve_units": (1 - SLEEVE) * INITIAL_CAPITAL / bpx},
        "nav": INITIAL_CAPITAL, "observation_days": 0, "signals": 0, "skipped": 0,
        "fills": [], "signal_rows": [], "observations": [],
        "pending_entry": None, "exit_date": None,
        "data_hashes": _hashes(data_dir), "code_sha": code_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "last_data_date": start.date().isoformat(),
    })
    _state_path(out_dir).write_text(json.dumps(state, indent=2), encoding="utf-8")
    with (out_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "START", "start_date": state["start_date"],
                            "recorded_at_utc": state["generated_at_utc"], "code_sha": code_sha}) + "\n")
    _write_dashboard(out_dir, state, dashboard_path)
    return state


def update(data_dir: Path, out_dir: Path, dashboard_path: Path | None = None):
    state = ensure(out_dir, dashboard_path)
    if state["status"] != "RUNNING":
        return state
    q = _load(data_dir / "QQQ.csv", "QQQ"); b = _load(data_dir / "BIL.csv", "BIL"); s = _load(data_dir / "SPY.csv", "SPY")
    q, b, s = build(q, b, s)
    start = pd.Timestamp(state["start_date"])
    cal = s.index[s.index >= start]
    if state.get("last_data_date"):
        cal = cal[cal > pd.Timestamp(state["last_data_date"])]
    c = COST_BPS / 10000
    pos = state["positions"]
    for dt in cal:
        if any(pd.isna(q.loc[dt, col]) or pd.isna(b.loc[dt, col]) for col in ("Open", "Close", "AdjClose")):
            raise RuntimeError(f"incomplete data at {dt.date()}")
        # missed orders are recorded, never filled at a later Open
        if state["pending_entry"] and dt.date().isoformat() > state["pending_entry"]:
            with (out_dir / "events.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"event": "MISSED_ENTRY", "planned": state["pending_entry"],
                                    "recorded_at_utc": datetime.now(timezone.utc).isoformat()}) + "\n")
            state["pending_entry"] = None
        if state["exit_date"] and dt.date().isoformat() > state["exit_date"]:
            with (out_dir / "events.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"event": "MISSED_EXIT", "planned": state["exit_date"],
                                    "recorded_at_utc": datetime.now(timezone.utc).isoformat()}) + "\n")
            state["exit_date"] = None
        # exit first
        if state["exit_date"] == dt.date().isoformat() and pos["qqq_units"] > 0:
            p = float(q.loc[dt, "AdjOpen"]); gross = pos["qqq_units"] * p; fee = gross * c; net = gross - fee
            bp = float(b.loc[dt, "AdjOpen"]); bn = net / (1 + c); units = bn / bp
            state["fills"].append({"date": dt.date().isoformat(), "leg": "SELL_QQQ", "quantity": pos["qqq_units"],
                                   "fill_price": p, "notional": gross, "cost": fee,
                                   "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                                   "status": "SIMULATED_PROSPECTIVE"})
            state["fills"].append({"date": dt.date().isoformat(), "leg": "BUY_BIL", "quantity": units,
                                   "fill_price": bp, "notional": bn, "cost": bn * c,
                                   "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                                   "status": "SIMULATED_PROSPECTIVE"})
            pos["qqq_units"] = 0.0; pos["bil_units"] = units; state["exit_date"] = None
        if state["pending_entry"] == dt.date().isoformat() and pos["qqq_units"] == 0:
            bp = float(b.loc[dt, "AdjOpen"]); p = float(q.loc[dt, "AdjOpen"])
            sold = pos["bil_units"]; value = sold * bp; bfee = value * c; qn = (value - bfee) / (1 + c); qu = qn / p
            state["fills"].append({"date": dt.date().isoformat(), "leg": "SELL_BIL", "quantity": sold,
                                   "fill_price": bp, "notional": value, "cost": bfee,
                                   "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                                   "status": "SIMULATED_PROSPECTIVE"})
            state["fills"].append({"date": dt.date().isoformat(), "leg": "BUY_QQQ", "quantity": qu,
                                   "fill_price": p, "notional": qn, "cost": qn * c,
                                   "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                                   "status": "SIMULATED_PROSPECTIVE"})
            pos["bil_units"] = 0.0; pos["qqq_units"] = qu; state["pending_entry"] = None
            idx = s.index.get_loc(dt)
            state["exit_date"] = s.index[min(idx + HOLD, len(s) - 1)].date().isoformat()
        sig = bool(q.Signal.loc[dt])
        if sig:
            state["signals"] += 1
            row = {"signal_date": dt.date().isoformat(), "regime": str(s.loc[dt, "Regime"]),
                   "status": "SIGNAL", "planned_entry": None}
            if state["exit_date"] or pos["qqq_units"] > 0:
                state["skipped"] += 1; row["status"] = "SKIPPED_OVERLAP"
            elif state["pending_entry"] is None:
                nxt = s.index[s.index > dt]
                if len(nxt): state["pending_entry"] = nxt[0].date().isoformat(); row["planned_entry"] = state["pending_entry"]
            state["signal_rows"].append(row)
        nav = pos["qqq_units"] * float(q.loc[dt, "AdjClose"]) + (pos["bil_units"] + pos["reserve_units"]) * float(b.loc[dt, "AdjClose"])
        state["nav"] = nav; state["observation_days"] += 1
        state["observations"].append({"date": dt.date().isoformat(), "nav": nav, "signal": sig})
        state["last_data_date"] = dt.date().isoformat()
        with (out_dir / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "OBSERVATION", "date": dt.date().isoformat(), "nav": nav,
                                "signal": sig, "recorded_at_utc": datetime.now(timezone.utc).isoformat()}) + "\n")
    state["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _state_path(out_dir).write_text(json.dumps(state, indent=2), encoding="utf-8")
    pd.DataFrame(state["fills"]).to_csv(out_dir / "fills.csv", index=False)
    pd.DataFrame(state["observations"]).to_csv(out_dir / "daily_nav.csv", index=False)
    pd.DataFrame(state["signal_rows"]).to_csv(out_dir / "signals.csv", index=False)
    _write_dashboard(out_dir, state, dashboard_path)
    return state


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start-prospective"); s.add_argument("--start-date", required=True)
    s.add_argument("--data-dir", type=Path, default=Path("data/research/qqq_transition_paper"))
    s.add_argument("--out-dir", type=Path, default=Path("qqq_transition_paper/prospective"))
    s.add_argument("--code-sha", default="unknown")
    u = sub.add_parser("update-prospective"); u.add_argument("--data-dir", type=Path, default=Path("data/research/qqq_transition_paper"))
    u.add_argument("--out-dir", type=Path, default=Path("qqq_transition_paper/prospective"))
    st = sub.add_parser("status"); st.add_argument("--out-dir", type=Path, default=Path("qqq_transition_paper/prospective"))
    a = p.parse_args()
    if a.cmd == "start-prospective":
        print(json.dumps(start(a.data_dir, a.out_dir, a.start_date, a.code_sha), indent=2))
    elif a.cmd == "update-prospective":
        print(json.dumps(update(a.data_dir, a.out_dir), indent=2))
    else:
        print(json.dumps(ensure(a.out_dir), indent=2))
