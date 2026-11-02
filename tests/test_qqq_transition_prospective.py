# -*- coding: utf-8 -*-
"""Tests for the forward-only prospective QQQ account."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from scripts.qqq_transition_paper import INITIAL_CAPITAL, SLEEVE
from scripts.qqq_transition_prospective import (
    ProspectiveError, add_sessions, append_event, ensure, rebuild_state_from_events, start, update,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "research" / "qqq_transition_paper"
ET = ZoneInfo("America/New_York")


def now(y, m, d, h=18):
    return datetime(y, m, d, h, 0, tzinfo=ET)


def test_default_state_is_not_started(tmp_path):
    state = ensure(tmp_path / "prospective", dashboard_path=tmp_path / "dash.json")
    assert state["status"] == "NOT_STARTED"
    assert state["prospective_clock_started"] is False
    assert state["start_date"] is None


def test_past_and_current_start_dates_rejected(tmp_path):
    with pytest.raises(ProspectiveError, match="future"):
        start(DATA, tmp_path / "a", "2026-10-29", "sha", now_et=now(2026, 10, 30), dashboard_path=tmp_path / "a.json")
    with pytest.raises(ProspectiveError, match="future"):
        start(DATA, tmp_path / "b", "2026-10-30", "sha", now_et=now(2026, 10, 30), dashboard_path=tmp_path / "b.json")


def test_next_future_session_accepted_and_uses_prior_bil_close(tmp_path):
    state = start(DATA, tmp_path / "p", "2026-11-02", "sha", now_et=now(2026, 10, 30),
                  dashboard_path=tmp_path / "dash.json")
    assert state["status"] == "RUNNING"
    assert state["start_date"] == "2026-11-02"
    assert state["initial_bil_session"] == "2026-10-30"
    bil = pd.read_csv(DATA / "BIL.csv")
    bil["Date"] = pd.to_datetime(bil["Date"], utc=True).dt.tz_convert(None).dt.normalize()
    row = bil[bil.Date == pd.Timestamp("2026-10-30")].iloc[0]
    assert state["initial_bil_price"] == pytest.approx(float(row["Adj Close"]))
    assert state["positions"]["qqq_units"] == 0
    assert state["fills"] == []
    assert state["code_sha"] == "sha"


def test_start_requires_non_unknown_code_sha(tmp_path):
    with pytest.raises(ProspectiveError, match="code_sha"):
        start(DATA, tmp_path / "p", "2026-11-02", "unknown", now_et=now(2026, 10, 30),
              dashboard_path=tmp_path / "dash.json")


def test_update_records_one_latest_session_and_is_idempotent(tmp_path):
    out = tmp_path / "p"
    start(DATA, out, "2026-10-30", "sha", now_et=now(2026, 10, 29), dashboard_path=tmp_path / "dash.json")
    first = update(DATA, out, now_et=now(2026, 10, 30), dashboard_path=tmp_path / "dash.json")
    second = update(DATA, out, now_et=now(2026, 10, 30), dashboard_path=tmp_path / "dash.json")
    assert first["observation_days"] == 1
    assert second["observation_days"] == 1
    assert first["fills"] == second["fills"]
    assert first["observations"] == second["observations"]
    assert first["observations"][0]["date"] == "2026-10-30"


def test_stale_data_fails_closed(tmp_path):
    out = tmp_path / "p"
    start(DATA, out, "2026-10-30", "sha", now_et=now(2026, 10, 29), dashboard_path=tmp_path / "dash.json")
    with pytest.raises(ProspectiveError, match="stale"):
        update(DATA, out, now_et=now(2026, 11, 2), dashboard_path=tmp_path / "dash.json")


def test_missed_entry_is_expired_not_filled(tmp_path):
    out = tmp_path / "p"
    state = start(DATA, out, "2026-10-29", "sha", now_et=now(2026, 10, 28), dashboard_path=tmp_path / "dash.json")
    state["pending_entry"] = "2026-10-29"
    state["last_data_date"] = "2026-10-28"
    append_event(out, "STATE", "2026-10-28", {"pending_entry": state["pending_entry"]}, state)
    updated = update(DATA, out, now_et=now(2026, 10, 30), dashboard_path=tmp_path / "dash.json")
    assert updated["fills"] == []
    assert "MISSED_ENTRY" in (out / "events.jsonl").read_text(encoding="utf-8")


def test_missed_exit_is_expired_not_filled(tmp_path):
    out = tmp_path / "p"
    state = start(DATA, out, "2026-10-29", "sha", now_et=now(2026, 10, 28), dashboard_path=tmp_path / "dash.json")
    state["exit_date"] = "2026-10-29"
    state["last_data_date"] = "2026-10-28"
    append_event(out, "STATE", "2026-10-28", {"exit_date": state["exit_date"]}, state)
    update(DATA, out, now_et=now(2026, 10, 30), dashboard_path=tmp_path / "dash.json")
    assert "MISSED_EXIT" in (out / "events.jsonl").read_text(encoding="utf-8")


def test_events_rebuild_state(tmp_path):
    out = tmp_path / "p"
    start(DATA, out, "2026-10-30", "sha", now_et=now(2026, 10, 29), dashboard_path=tmp_path / "dash.json")
    state = update(DATA, out, now_et=now(2026, 10, 30), dashboard_path=tmp_path / "dash.json")
    rebuilt = rebuild_state_from_events(out)
    assert rebuilt["nav"] == state["nav"]
    assert rebuilt["observation_days"] == state["observation_days"]


def test_committed_prospective_is_not_started():
    root = ROOT / "qqq_transition_paper" / "prospective"
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "NOT_STARTED"
    assert state["prospective_clock_started"] is False
    dash = json.loads((ROOT / "dashboard" / "data" / "qqq_transition_paper_prospective.json").read_text())
    assert dash["prospective_clock_started"] is False


def test_dashboard_has_two_isolated_panels():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app.js").read_text(encoding="utf-8")
    assert 'id="qqqPaperSec"' in html and 'id="qqqProspectiveSec"' in html
    assert "qqq_transition_paper.json" in js and "qqq_transition_paper_prospective.json" in js


def _truncate_copy(tmp_path, last_date):
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    for t in ("QQQ", "BIL", "SPY"):
        df = pd.read_csv(DATA / f"{t}.csv")
        dates = pd.to_datetime(df["Date"], utc=True).dt.tz_convert(None).dt.normalize()
        df = df[dates <= pd.Timestamp(last_date)]
        df.to_csv(d / f"{t}.csv", index=False)
    return d


def test_full_signal_intent_entry_hold_exit(tmp_path):
    import json
    # Known locked signal: 2025-04-03 -> entry 2025-04-04 -> exit 2025-04-11.
    S, E, X = "2025-04-03", "2025-04-04", "2025-04-11"
    out = tmp_path / "p"
    d1 = _truncate_copy(tmp_path / "s0", "2025-04-02")
    start(d1, out, S, "sha", now_et=now(2025, 4, 2), dashboard_path=tmp_path / "dash.json")
    dS = _truncate_copy(tmp_path / "s1", S)
    s1 = update(dS, out, now_et=now(2025, 4, 3), dashboard_path=tmp_path / "dash.json")
    assert s1["pending_entry"] == E
    d2 = _truncate_copy(tmp_path / "e", E)
    s2 = update(d2, out, now_et=now(2025, 4, 4), dashboard_path=tmp_path / "dash.json")
    assert len(s2["fills"]) == 2
    assert [f["leg"] for f in s2["fills"]] == ["SELL_BIL", "BUY_QQQ"]
    assert s2["exit_date"] == X
    assert s2["positions"]["qqq_units"] > 0
    d3 = _truncate_copy(tmp_path / "x", X)
    s3 = update(d3, out, now_et=now(2025, 4, 11), dashboard_path=tmp_path / "dash.json")
    assert [f["leg"] for f in s3["fills"]] == ["SELL_BIL", "BUY_QQQ", "SELL_QQQ", "BUY_BIL"]
    assert s3["positions"]["qqq_units"] == 0
    assert s3["status"] == "RUNNING"
    rebuilt = rebuild_state_from_events(out)
    assert rebuilt["fills"] == s3["fills"]
    assert rebuilt["nav"] == s3["nav"]
    assert rebuilt["positions"] == s3["positions"]
    assert rebuilt["signal_rows"] == s3["signal_rows"]
    assert rebuilt["exit_date"] == s3["exit_date"]
    assert rebuilt["observation_days"] == s3["observation_days"]


def test_missed_exit_halts_and_retains_position(tmp_path):
    S, E = "2025-04-03", "2025-04-04"
    out = tmp_path / "p"
    d1 = _truncate_copy(tmp_path / "ha", "2025-04-02")
    start(d1, out, S, "sha", now_et=now(2025, 4, 2), dashboard_path=tmp_path / "dash.json")
    dS = _truncate_copy(tmp_path / "hb", S)
    update(dS, out, now_et=now(2025, 4, 3), dashboard_path=tmp_path / "dash.json")
    d2 = _truncate_copy(tmp_path / "b", E)
    update(d2, out, now_et=now(2025, 4, 4), dashboard_path=tmp_path / "dash.json")
    state = json.loads((out / "state.json").read_text())
    qunits = state["positions"]["qqq_units"]
    assert qunits > 0
    dlate = _truncate_copy(tmp_path / "c", "2025-04-14")
    halted = update(dlate, out, now_et=now(2025, 4, 14), dashboard_path=tmp_path / "dash.json")
    assert halted["status"] == "HALTED_MISSED_EXIT"
    assert halted["positions"]["qqq_units"] == qunits
    assert "MISSED_EXIT" in (out / "events.jsonl").read_text()
    assert update(dlate, out, now_et=now(2025, 4, 14), dashboard_path=tmp_path / "dash.json") == halted


def test_missing_latest_qqq_or_bil_fails_closed(tmp_path):
    d = _truncate_copy(tmp_path, "2025-04-03")
    for t in ("QQQ", "BIL"):
        bad = tmp_path / f"bad_{t}"
        bad.mkdir()
        for x in ("QQQ", "BIL", "SPY"):
            df = pd.read_csv(d / f"{x}.csv")
            if x == t:
                df = df.iloc[:-1]
            df.to_csv(bad / f"{x}.csv", index=False)
        out = tmp_path / f"out_{t}"
        start(d, out, "2025-04-03", "sha", now_et=now(2025, 4, 2), dashboard_path=tmp_path / f"{t}.json")
        with pytest.raises(ProspectiveError):
            update(bad, out, now_et=now(2025, 4, 3), dashboard_path=tmp_path / f"{t}.json")


def test_interrupted_two_leg_transaction_fails_rebuild(tmp_path):
    import json
    S, E = "2025-04-03", "2025-04-04"
    out = tmp_path / "p"
    d1 = _truncate_copy(tmp_path / "i0", "2025-04-02")
    start(d1, out, S, "sha", now_et=now(2025, 4, 2), dashboard_path=tmp_path / "dash.json")
    dS = _truncate_copy(tmp_path / "i1", S)
    update(dS, out, now_et=now(2025, 4, 3), dashboard_path=tmp_path / "dash.json")
    dE = _truncate_copy(tmp_path / "i2", E)
    update(dE, out, now_et=now(2025, 4, 4), dashboard_path=tmp_path / "dash.json")
    lines = [x for x in (out / "events.jsonl").read_text().splitlines() if x.strip()]
    # Drop the second FILL event; the last state snapshot still contains both legs.
    drop = None
    for i in range(len(lines) - 1, -1, -1):
        if json.loads(lines[i])["event_type"] == "FILL":
            drop = i
            break
    assert drop is not None
    (out / "events.jsonl").write_text("\n".join(lines[:drop] + lines[drop + 1:]) + "\n", encoding="utf-8")
    with pytest.raises(ProspectiveError, match="interrupted"):
        rebuild_state_from_events(out)


def test_future_offsets_use_xnys_holidays():
    assert str(add_sessions("2024-07-03", 1).date()) == "2024-07-05"
    assert str(add_sessions("2024-12-24", 1).date()) == "2024-12-26"
    assert str(add_sessions("2024-07-03", 5).date()) == "2024-07-11"
