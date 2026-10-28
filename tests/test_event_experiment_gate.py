# -*- coding: utf-8 -*-
"""Tests for the hard event-experiment gate."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_experiment_gate as gate  # noqa: E402


def events(n=200, days=400):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [{"event_id": f"e{i}", "first_seen_at_utc": (start + timedelta(days=days * i / max(n - 1, 1))).isoformat()} for i in range(n)]


def readiness(n=200, status="ready"):
    return {"events": [{
        "event_id": f"e{i}", "status": status, "entry_bar_date": "2026-01-01",
        "result_1d_date": "2026-01-02", "result_5d_date": "2026-01-08",
    } for i in range(n)]}


def config(**overrides):
    c = {"oos_windows": 2, "cost_bps": [5, 10, 20], "horizons": [1, 5],
         "multiple_testing": "benjamini-hochberg", "time_split": {"train_end": "2025-06-30"}}
    c.update(overrides)
    return c


def test_eligible_requires_all_preregistered_conditions():
    out = gate.evaluate(events(), readiness(), config())
    assert out["status"] == "eligible"
    assert out["exit_code"] == 0


def test_35_short_sample_is_not_eligible():
    out = gate.evaluate(events(35, 30), readiness(35), config())
    assert out["status"] == "not_eligible"
    assert "unique_events_below_200" in out["reasons"]


def test_pending_results_cannot_pass():
    out = gate.evaluate(events(), readiness(status="pending_future_entry_bar"), config())
    assert out["status"] == "pending"
    assert "pending_event_results" in out["reasons"]


def test_missing_plus5_and_bad_config_fail():
    r = readiness()
    for row in r["events"]:
        row["result_5d_date"] = None
    out = gate.evaluate(events(), r, config(cost_bps=[5], multiple_testing="none"))
    assert out["status"] == "not_eligible"
    assert "plus_5_results_below_200" in out["reasons"]
    assert "cost_sensitivity_incomplete" in out["reasons"]
    assert "multiple_testing_not_preregistered_bh" in out["reasons"]


def test_excluded_events_fail_closed():
    r = readiness()
    r["events"][0]["status"] = "excluded"
    out = gate.evaluate(events(), r, config())
    assert out["status"] == "not_eligible"
    assert "excluded_events_present" in out["reasons"]
