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
    ProspectiveError, ensure, rebuild_state_from_events, start, update,
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
    (out / "state.json").write_text(json.dumps(state), encoding="utf-8")
    updated = update(DATA, out, now_et=now(2026, 10, 30), dashboard_path=tmp_path / "dash.json")
    assert updated["fills"] == []
    assert "MISSED_ENTRY" in (out / "events.jsonl").read_text(encoding="utf-8")


def test_missed_exit_is_expired_not_filled(tmp_path):
    out = tmp_path / "p"
    state = start(DATA, out, "2026-10-29", "sha", now_et=now(2026, 10, 28), dashboard_path=tmp_path / "dash.json")
    state["exit_date"] = "2026-10-29"
    state["last_data_date"] = "2026-10-28"
    (out / "state.json").write_text(json.dumps(state), encoding="utf-8")
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
