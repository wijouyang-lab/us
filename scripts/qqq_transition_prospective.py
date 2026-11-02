#!/usr/bin/env python3
"""Forward-only QQQ TRANSITION simulated account.

Default state is NOT_STARTED. No broker connection, no orders, no historical
backfill into the prospective account.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from scripts.qqq_transition_paper import (
    COST_BPS, HOLD, INITIAL_CAPITAL, SLEEVE, STRATEGY_FINGERPRINT,
    _load, build,
)

ET = ZoneInfo("America/New_York")
DEFAULT_STATE = {
    "schema": "qqq-transition-prospective-v2",
    "status": "NOT_STARTED",
    "prospective_clock_started": False,
    "start_date": None,
    "initial_capital": INITIAL_CAPITAL,
    "sleeve_fraction": SLEEVE,
    "cost_bps_per_leg": COST_BPS,
    "strategy_fingerprint": STRATEGY_FINGERPRINT,
    "positions": {"cash": 0.0, "qqq_units": 0.0, "bil_units": 0.0, "reserve_units": 0.0},
    "initial_bil_price": None,
    "initial_bil_session": None,
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
    "last_data_date": None,
}


class ProspectiveError(RuntimeError):
    pass


def _now_et(now_et: datetime | None = None) -> datetime:
    v = now_et or datetime.now(ET)
    if v.tzinfo is None:
        raise ProspectiveError("now_et must be timezone-aware")
    return v.astimezone(ET)


def _calendar():
    return xcals.get_calendar("XNYS")


def expected_completed_session(now_et: datetime | None = None):
    now = _now_et(now_et)
    cal = _calendar()
    today = pd.Timestamp(now.date())
    sessions = cal.sessions
    if today in sessions:
        close = cal.session_close(today).tz_convert(ET)
        if now >= close:
            return today
    return cal.previous_session(today)


def next_future_session(now_et: datetime | None = None):
    now = _now_et(now_et)
    cal = _calendar()
    return cal.next_session(pd.Timestamp(now.date()))


def _state_path(out_dir: Path) -> Path:
    return out_dir / "state.json"


def _hashes(data_dir: Path) -> dict:
    return {t: hashlib.sha256((data_dir / f"{t}.csv").read_bytes()).hexdigest() for t in ("QQQ", "BIL", "SPY")}


def _event_id(kind: str, session: str | None, core: dict) -> str:
    raw = json.dumps({"type": kind, "session": session, "core": core}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def append_event(out_dir: Path, kind: str, session: str | None, core: dict, state: dict):
    path = out_dir / "events.jsonl"
    eid = _event_id(kind, session, core)
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.add(json.loads(line)["event_id"])
    if eid in existing:
        return False
    rec = {"event_id": eid, "event_type": kind, "session_date": session,
           "recorded_at_utc": datetime.now(ET).astimezone().isoformat(),
           "core": core, "state": state}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return True


def rebuild_state_from_events(out_dir: Path) -> dict:
    path = out_dir / "events.jsonl"
    if not path.exists():
        raise ProspectiveError("no event log")
    state = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        state = rec["state"]
    if state is None:
        raise ProspectiveError("empty event log")
    return state


def _write_dashboard(out_dir: Path, state: dict, dashboard_path: Path | None = None):
    d = Path(dashboard_path) if dashboard_path else Path("dashboard/data/qqq_transition_paper_prospective.json")
    d.parent.mkdir(parents=True, exist_ok=True)
    navs = [x["nav"] for x in state.get("observations", [])]
    mdd = float((pd.Series(navs) / pd.Series(navs).cummax() - 1).min()) if navs else 0.0
    payload = {
        "mode": "PROSPECTIVE_SIMULATION", "status": state["status"],
        "prospective_clock_started": state["prospective_clock_started"],
        "start_date": state["start_date"], "initial_capital": state["initial_capital"],
        "initial_bil_price": state.get("initial_bil_price"),
        "initial_bil_session": state.get("initial_bil_session"),
        "nav": state["nav"], "return_pct": state["nav"] / state["initial_capital"] - 1,
        "cash": state["positions"]["cash"], "qqq_units": state["positions"]["qqq_units"],
        "bil_units": state["positions"]["bil_units"] + state["positions"]["reserve_units"],
        "observation_days": state["observation_days"], "signals": state["signals"],
        "skipped": state["skipped"], "max_drawdown": mdd,
        "total_cost": sum(x.get("cost", 0) for x in state["fills"]),
        "last_data_date": state.get("last_data_date"), "recent_fills": state["fills"][-4:],
        "recent_signals": state["signal_rows"][-5:], "code_sha": state.get("code_sha"),
        "data_hashes": state.get("data_hashes", {}), "updated_at_utc": state.get("generated_at_utc"),
    }
    d.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure(out_dir: Path, dashboard_path: Path | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = _state_path(out_dir)
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_STATE, indent=2), encoding="utf-8")
        _write_dashboard(out_dir, DEFAULT_STATE, dashboard_path)
    return json.loads(p.read_text(encoding="utf-8"))


def _fresh_data(data_dir: Path, now_et: datetime, require_latest: bool = True):
    q = _load(data_dir / "QQQ.csv", "QQQ")
    b = _load(data_dir / "BIL.csv", "BIL")
    s = _load(data_dir / "SPY.csv", "SPY")
    q, b, s = build(q, b, s)
    expected = expected_completed_session(now_et)
    latest = s.index[-1]
    if require_latest and latest != expected:
        raise ProspectiveError(f"stale market data: latest={latest.date()} expected={expected.date()}")
    return q, b, s


def start(data_dir: Path, out_dir: Path, start_date: str, code_sha: str,
          now_et: datetime | None = None, dashboard_path: Path | None = None):
    if not code_sha or code_sha == "unknown":
        raise ProspectiveError("code_sha is required and cannot be unknown")
    state = ensure(out_dir, dashboard_path)
    if state["status"] != "NOT_STARTED":
        raise ProspectiveError("prospective account already started")
    now = _now_et(now_et)
    cal = _calendar()
    start = pd.Timestamp(start_date)
    if start <= pd.Timestamp(now.date()):
        raise ProspectiveError("start_date must be a future SPY session")
    if start not in cal.sessions:
        raise ProspectiveError("start_date is not a valid SPY session")
    q, b, s = build(_load(data_dir / "QQQ.csv", "QQQ"), _load(data_dir / "BIL.csv", "BIL"),
                    _load(data_dir / "SPY.csv", "SPY"))
    prev = s.index[s.index < start]
    if prev.empty:
        raise ProspectiveError("no completed session before start")
    last = prev[-1]
    if last != expected_completed_session(now):
        raise ProspectiveError("start data is stale: last completed session mismatch")
    bpx = float(b.loc[last, "AdjClose"])
    if not bpx > 0:
        raise ProspectiveError("invalid initial BIL price")
    state.update({
        "status": "RUNNING", "prospective_clock_started": True, "start_date": start.date().isoformat(),
        "positions": {"cash": 0.0, "qqq_units": 0.0,
                      "bil_units": SLEEVE * INITIAL_CAPITAL / bpx,
                      "reserve_units": (1 - SLEEVE) * INITIAL_CAPITAL / bpx},
        "initial_bil_price": bpx, "initial_bil_session": last.date().isoformat(),
        "nav": INITIAL_CAPITAL, "observation_days": 0, "signals": 0, "skipped": 0,
        "fills": [], "signal_rows": [], "observations": [],
        "pending_entry": None, "exit_date": None, "last_data_date": last.date().isoformat(),
        "data_hashes": _hashes(data_dir), "code_sha": code_sha,
        "generated_at_utc": datetime.now(ET).astimezone().isoformat(),
    })
    _state_path(out_dir).write_text(json.dumps(state, indent=2), encoding="utf-8")
    append_event(out_dir, "START", state["start_date"], {
        "initial_capital": INITIAL_CAPITAL, "sleeve": SLEEVE,
        "initial_bil_session": state["initial_bil_session"],
        "initial_bil_price": bpx, "code_sha": code_sha, "data_hashes": state["data_hashes"]}, state)
    _write_dashboard(out_dir, state, dashboard_path)
    return state


def update(data_dir: Path, out_dir: Path, now_et: datetime | None = None, dashboard_path: Path | None = None):
    state = ensure(out_dir, dashboard_path)
    if state["status"] != "RUNNING":
        return state
    now = _now_et(now_et)
    q, b, s = _fresh_data(data_dir, now)
    latest = s.index[-1]
    last = pd.Timestamp(state["last_data_date"])
    if latest <= last:
        return state
    # Do not replay missed intermediate sessions.
    cal = _calendar()
    missed_sessions = cal.sessions_in_range(last + pd.Timedelta(days=1), latest - pd.Timedelta(days=1))
    if len(missed_sessions):
        append_event(out_dir, "MISSED_SESSIONS", latest.date().isoformat(),
                     {"sessions": [x.date().isoformat() for x in missed_sessions]}, state)
    pos = state["positions"]
    c = COST_BPS / 10000
    latest_s = latest.date().isoformat()
    # Expire orders older than the current latest session; never fill them later.
    if state["pending_entry"] and state["pending_entry"] < latest_s:
        append_event(out_dir, "MISSED_ENTRY", latest_s, {"planned": state["pending_entry"]}, state)
        state["pending_entry"] = None
    if state["exit_date"] and state["exit_date"] < latest_s:
        append_event(out_dir, "MISSED_EXIT", latest_s, {"planned": state["exit_date"]}, state)
        state["exit_date"] = None
    if state["exit_date"] == latest_s and pos["qqq_units"] > 0:
        p = float(q.loc[latest, "AdjOpen"]); gross = pos["qqq_units"] * p; fee = gross * c; net = gross - fee
        bp = float(b.loc[latest, "AdjOpen"]); bn = net / (1 + c); units = bn / bp
        fill_q = {"date": latest_s, "leg": "SELL_QQQ", "quantity": pos["qqq_units"], "fill_price": p,
                  "notional": gross, "cost": fee, "recorded_at_utc": now.isoformat(),
                  "status": "SIMULATED_PROSPECTIVE"}
        fill_b = {"date": latest_s, "leg": "BUY_BIL", "quantity": units, "fill_price": bp,
                  "notional": bn, "cost": bn * c, "recorded_at_utc": now.isoformat(),
                  "status": "SIMULATED_PROSPECTIVE"}
        state["fills"] += [fill_q, fill_b]
        append_event(out_dir, "FILL", latest_s, fill_q, state); append_event(out_dir, "FILL", latest_s, fill_b, state)
        pos["qqq_units"] = 0.0; pos["bil_units"] = units; state["exit_date"] = None
    if state["pending_entry"] == latest_s and pos["qqq_units"] == 0:
        p = float(q.loc[latest, "AdjOpen"]); bp = float(b.loc[latest, "AdjOpen"])
        sold = pos["bil_units"]; value = sold * bp; bfee = value * c; qn = (value - bfee) / (1 + c); qu = qn / p
        f1 = {"date": latest_s, "leg": "SELL_BIL", "quantity": sold, "fill_price": bp,
              "notional": value, "cost": bfee, "recorded_at_utc": now.isoformat(),
              "status": "SIMULATED_PROSPECTIVE"}
        f2 = {"date": latest_s, "leg": "BUY_QQQ", "quantity": qu, "fill_price": p,
              "notional": qn, "cost": qn * c, "recorded_at_utc": now.isoformat(),
              "status": "SIMULATED_PROSPECTIVE"}
        state["fills"] += [f1, f2]
        append_event(out_dir, "FILL", latest_s, f1, state); append_event(out_dir, "FILL", latest_s, f2, state)
        pos["bil_units"] = 0.0; pos["qqq_units"] = qu; state["pending_entry"] = None
        idx = s.index.get_loc(latest)
        state["exit_date"] = s.index[min(idx + HOLD, len(s) - 1)].date().isoformat()
    sig = bool(q.Signal.loc[latest])
    if sig:
        state["signals"] += 1
        row = {"signal_date": latest_s, "regime": str(s.loc[latest, "Regime"]), "status": "SIGNAL",
               "planned_entry": None}
        if state["exit_date"] or pos["qqq_units"] > 0:
            state["skipped"] += 1; row["status"] = "SKIPPED_OVERLAP"
        elif state["pending_entry"] is None:
            nxt = s.index[s.index > latest]
            if len(nxt):
                state["pending_entry"] = nxt[0].date().isoformat(); row["planned_entry"] = state["pending_entry"]
                append_event(out_dir, "ORDER_INTENT", latest_s, row, state)
        state["signal_rows"].append(row)
        append_event(out_dir, "SIGNAL", latest_s, row, state)
    nav = pos["qqq_units"] * float(q.loc[latest, "AdjClose"]) + (pos["bil_units"] + pos["reserve_units"]) * float(b.loc[latest, "AdjClose"])
    state["nav"] = nav; state["observation_days"] += 1; state["last_data_date"] = latest_s
    obs = {"date": latest_s, "nav": nav, "signal": sig, "regime": str(s.loc[latest, "Regime"])}
    state["observations"].append(obs)
    append_event(out_dir, "OBSERVATION", latest_s, obs, state)
    append_event(out_dir, "DAILY_NAV", latest_s, {"nav": nav}, state)
    state["generated_at_utc"] = datetime.now(ET).astimezone().isoformat()
    _state_path(out_dir).write_text(json.dumps(state, indent=2), encoding="utf-8")
    for name, rows in (("fills", state["fills"]), ("daily_nav", state["observations"]),
                       ("signals", state["signal_rows"])):
        pd.DataFrame(rows).to_csv(out_dir / f"{name}.csv", index=False)
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
