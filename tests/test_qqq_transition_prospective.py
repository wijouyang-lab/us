# -*- coding: utf-8 -*-
"""Tests for prospective QQQ paper account initialization/defaults."""
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.qqq_transition_paper import INITIAL_CAPITAL, SLEEVE
from scripts.qqq_transition_prospective import ensure, start, update

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "research" / "qqq_transition_paper"


def test_default_state_is_not_started(tmp_path):
    state = ensure(tmp_path / "prospective", dashboard_path=tmp_path / "dash.json")
    assert state["status"] == "NOT_STARTED"
    assert state["prospective_clock_started"] is False
    assert state["start_date"] is None


def test_start_locks_capital_sleeve_and_hashes(tmp_path):
    out = tmp_path / "prospective"
    state = start(DATA, out, "2026-10-29", "test-sha", dashboard_path=tmp_path / "dash.json")
    assert state["status"] == "RUNNING"
    assert state["prospective_clock_started"] is True
    assert state["start_date"] == "2026-10-29"
    assert state["initial_capital"] == INITIAL_CAPITAL
    assert state["sleeve_fraction"] == SLEEVE
    assert state["positions"]["qqq_units"] == 0
    assert state["positions"]["bil_units"] > 0
    assert state["fills"] == []
    assert len(state["data_hashes"]) == 3


def test_update_records_zero_signal_day_and_is_idempotent(tmp_path):
    out = tmp_path / "prospective"
    start(DATA, out, "2026-10-29", "test-sha", dashboard_path=tmp_path / "dash.json")
    first = update(DATA, out, dashboard_path=tmp_path / "dash.json")
    second = update(DATA, out, dashboard_path=tmp_path / "dash.json")
    assert first["observation_days"] == 1
    assert second["observation_days"] == 1
    assert first["fills"] == second["fills"]
    assert first["observations"] == second["observations"]
    assert first["observations"][0]["date"] == "2026-10-30"


def test_committed_prospective_is_not_started():
    root = ROOT / "qqq_transition_paper" / "prospective"
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "NOT_STARTED"
    assert state["prospective_clock_started"] is False
    dash = json.loads((ROOT / "dashboard" / "data" / "qqq_transition_paper_prospective.json").read_text())
    assert dash["prospective_clock_started"] is False


def test_missed_entry_is_expired_not_filled(tmp_path):
    out = tmp_path / "prospective"
    state = start(DATA, out, "2026-10-28", "test-sha", dashboard_path=tmp_path / "dash.json")
    state["pending_entry"] = "2026-10-27"
    state["last_data_date"] = "2026-10-29"
    (out / "state.json").write_text(json.dumps(state), encoding="utf-8")
    before = len(state["fills"])
    updated = update(DATA, out, dashboard_path=tmp_path / "dash.json")
    assert len(updated["fills"]) == before
    events = (out / "events.jsonl").read_text(encoding="utf-8")
    assert "MISSED_ENTRY" in events


def test_historical_replay_does_not_populate_prospective(tmp_path):
    state = start(DATA, tmp_path / "prospective", "2026-10-29", "test-sha", dashboard_path=tmp_path / "dash.json")
    assert state["fills"] == []
    assert state["observation_days"] == 0


def test_dashboard_has_two_isolated_panels():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app.js").read_text(encoding="utf-8")
    assert 'id="qqqPaperSec"' in html and 'id="qqqProspectiveSec"' in html
    assert "qqq_transition_paper.json" in js
    assert "qqq_transition_paper_prospective.json" in js
