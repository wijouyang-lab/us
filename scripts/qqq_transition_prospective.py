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
import numpy as np
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


def add_sessions(date, count: int):
    d = pd.Timestamp(date)
    cal = _calendar()
    for _ in range(count):
        d = cal.next_session(d)
    return d


def _session_hash(q, b, s, dt) -> str:
    payload = []
    for frame, name in ((q, "QQQ"), (b, "BIL"), (s, "SPY")):
        payload.append([name, str(dt.date()), float(frame.loc[dt, "Open"]),
                        float(frame.loc[dt, "Close"]), float(frame.loc[dt, "AdjClose"])])
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
    """Rebuild from validated atomic state checkpoints, then reconcile counts.

    Every event carries the post-event state snapshot. This function validates the
    append-only sequence and checks that snapshots contain every FILL/OBSERVATION
    event; an interrupted two-leg transaction therefore fails closed.
    """
    path = out_dir / "events.jsonl"
    if not path.exists():
        raise ProspectiveError("no event log")
    state = None
    ids = set()
    fill_events = obs_events = signal_events = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProspectiveError("corrupt JSONL event") from exc
        eid = rec.get("event_id")
        if not eid or eid in ids:
            raise ProspectiveError("duplicate or missing event_id")
        ids.add(eid)
        kind = rec.get("event_type")
        if kind == "FILL":
            fill_events += 1
        elif kind == "OBSERVATION":
            obs_events += 1
        elif kind == "SIGNAL":
            signal_events += 1
        state = rec.get("state")
        if not isinstance(state, dict):
            raise ProspectiveError("event missing state snapshot")
    if state is None:
        raise ProspectiveError("empty event log")
    if len(state.get("fills", [])) != fill_events:
        raise ProspectiveError("fill state/event mismatch (possible interrupted transaction)")
    if len(state.get("observations", [])) != obs_events:
        raise ProspectiveError("observation state/event mismatch")
    if state.get("observation_days") != obs_events:
        raise ProspectiveError("observation_days mismatch")
    if len(state.get("signal_rows", [])) != signal_events:
        raise ProspectiveError("signal state/event mismatch")
    if not np.isfinite(state.get("nav", float("nan"))):
        raise ProspectiveError("non-finite NAV in event state")
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
    latest = min(q.index[-1], b.index[-1], s.index[-1])
    if require_latest and latest != expected:
        raise ProspectiveError(f"stale market data: common_latest={latest.date()} expected={expected.date()}")
    if q.index[-1] != latest or b.index[-1] != latest or s.index[-1] != latest:
        raise ProspectiveError("incomplete common latest session across QQQ/BIL/SPY")
    for frame, name in ((q, "QQQ"), (b, "BIL"), (s, "SPY")):
        vals = frame.loc[latest, ["Open", "Close", "AdjClose"]]
        if not all(pd.notna(vals) & (vals > 0)):
            raise ProspectiveError(f"{name}: missing/non-positive latest session {latest.date()}")
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
    if state["status"] == "HALTED_MISSED_EXIT":
        return state
    if state["status"] != "RUNNING":
        return state
    if (out_dir / "events.jsonl").exists():
        state = rebuild_state_from_events(out_dir)
        _state_path(out_dir).write_text(json.dumps(state, indent=2), encoding="utf-8")
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
        state["status"] = "HALTED_MISSED_EXIT"
        state["manual_review_required"] = True
        state["halt_reason"] = f"missed exit {state['exit_date']}"
        append_event(out_dir, "MISSED_EXIT", latest_s, {"planned": state["exit_date"],
                                                        "position_retained": True}, state)
        state["generated_at_utc"] = datetime.now(ET).astimezone().isoformat()
        _state_path(out_dir).write_text(json.dumps(state, indent=2), encoding="utf-8")
        _write_dashboard(out_dir, state, dashboard_path)
        return state
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
        state["exit_date"] = add_sessions(latest, HOLD).date().isoformat()
    sig = bool(q.Signal.loc[latest])
    if sig:
        state["signals"] += 1
        row = {"signal_date": latest_s, "regime": str(s.loc[latest, "Regime"]), "status": "SIGNAL",
               "planned_entry": None}
        if state["exit_date"] or pos["qqq_units"] > 0:
            state["skipped"] += 1; row["status"] = "SKIPPED_OVERLAP"
        elif state["pending_entry"] is None:
            nxt = _calendar().next_session(latest)
            state["pending_entry"] = nxt.date().isoformat()
            row["planned_entry"] = state["pending_entry"]
            append_event(out_dir, "ORDER_INTENT", latest_s, row, state)
        state["signal_rows"].append(row)
        append_event(out_dir, "SIGNAL", latest_s, row, state)
    nav = pos["qqq_units"] * float(q.loc[latest, "AdjClose"]) + (pos["bil_units"] + pos["reserve_units"]) * float(b.loc[latest, "AdjClose"])
    if not np.isfinite(nav):
        raise ProspectiveError("non-finite NAV")
    state["nav"] = nav; state["observation_days"] += 1; state["last_data_date"] = latest_s
    obs = {"date": latest_s, "nav": nav, "signal": sig, "regime": str(s.loc[latest, "Regime"]),
           "source_hash": _session_hash(q, b, s, latest), "data_asof": latest_s}
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


def review_halt(out_dir: Path, note: str, dashboard_path: Path | None = None):
    state = ensure(out_dir, dashboard_path)
    if state["status"] != "HALTED_MISSED_EXIT":
        raise ProspectiveError("account is not halted")
    if not note.strip():
        raise ProspectiveError("review note is required")
    state["halt_reviewed"] = True
    state["halt_review_note"] = note.strip()
    append_event(out_dir, "HALT_REVIEW", state.get("last_data_date"), {"note": note.strip()}, state)
    _state_path(out_dir).write_text(json.dumps(state, indent=2), encoding="utf-8")
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
    rv = sub.add_parser("review-halt"); rv.add_argument("--out-dir", type=Path, default=Path("qqq_transition_paper/prospective"))
    rv.add_argument("--note", required=True)
    a = p.parse_args()
    if a.cmd == "start-prospective":
        print(json.dumps(start(a.data_dir, a.out_dir, a.start_date, a.code_sha), indent=2))
    elif a.cmd == "update-prospective":
        print(json.dumps(update(a.data_dir, a.out_dir), indent=2))
    elif a.cmd == "review-halt":
        print(json.dumps(review_halt(a.out_dir, a.note), indent=2))
    else:
        print(json.dumps(ensure(a.out_dir), indent=2))
