# -*- coding: utf-8 -*-
"""Tests for Fed event expected trading-date mapping; no prices/network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_label_plan as ep  # noqa: E402


def event(published="2026-10-28T14:00:00Z"):
    return {"event_id": "e1", "published_at_utc": published,
            "observation_mode": "retrospective_backfill"}


def row(published, rule="next_open"):
    return ep.map_event(event(published), ep.xcals.get_calendar("XNYS"), rule)


def test_conservative_open_rule_premarket_same_session():
    assert row("2026-10-28T12:00:00Z")["entry_date"] == "2026-10-28"
    assert row("2026-10-28T12:00:00Z")["entry_time_utc"] == "2026-10-28T13:30:00Z"


def test_intraday_at_or_after_open_uses_next_session_open():
    assert row("2026-10-28T18:00:00Z")["entry_date"] == "2026-10-29"
    assert row("2026-10-28T20:00:00Z")["entry_date"] == "2026-10-29"
    assert row("2026-10-28T21:00:00Z")["entry_date"] == "2026-10-29"


def test_legacy_close_rule_has_different_mapping():
    assert row("2026-10-28T18:00:00Z", "legacy_close")["entry_date"] == "2026-10-28"
    assert row("2026-10-28T18:00:00Z", "next_open")["entry_date"] == "2026-10-29"


def test_weekend_and_holiday_use_next_session_open():
    assert row("2026-10-31T12:00:00Z")["entry_date"] == "2026-11-02"
    assert row("2026-11-26T12:00:00Z")["entry_date"] == "2026-11-27"


def test_early_close_after_close_uses_next_session():
    assert row("2026-11-27T19:00:00Z")["entry_date"] == "2026-11-30"


def test_plus1_and_plus5_are_entry_plus_sessions():
    out = row("2026-10-28T12:00:00Z")
    assert out["plus1_date"] == "2026-10-29"
    assert out["plus5_date"] == "2026-11-04"
    out = row("2026-10-28T18:00:00Z")
    assert out["plus1_date"] == "2026-10-30"
    assert out["plus5_date"] == "2026-11-05"


def test_cross_year():
    assert row("2026-12-31T21:00:00Z")["entry_date"] == "2027-01-04"


def test_missing_time_is_not_filled():
    out = row(None)
    assert out["entry_date"] is None
    assert out["label_status"] == "missing_event_time"
    assert out["missing_reason"] == "missing_published_at"


def test_returns_are_not_created_without_price_provider():
    out = row("2026-10-28T14:00:00Z")
    assert out["return_1d"] is None
    assert out["return_5d"] is None
    assert out["label_status"] == "pending_price_provider"


def test_entry_price_point_is_explicit():
    assert row("2026-10-28T18:00:00Z")["entry_price_point"] == "open"
    assert row("2026-10-28T18:00:00Z", "legacy_close")["entry_price_point"] == "close"
def test_retrospective_available_at_is_unknown_not_publication():
    out = row("2026-10-28T12:00:00Z")
    assert out["available_at"] is None
    assert out["availability_known"] is False
    assert out["mapping_time"] == "2026-10-28T12:00:00Z"


def test_pit_uses_first_seen_as_available():
    e = event("2026-10-28T12:00:00Z")
    e["observation_mode"] = "forward_pit"
    e["first_seen_at_utc"] = "2026-10-28T14:00:00Z"
    e["decision_at"] = "2026-10-28T14:00:00Z"
    out = ep.map_event(e, ep.xcals.get_calendar("XNYS"))
    assert out["available_at"] == "2026-10-28T14:00:00Z"
    assert out["availability_known"] is True
    assert out["entry_date"] == "2026-10-29"  # after open


def test_pit_missing_first_seen_fails():
    e = event("2026-10-28T12:00:00Z")
    e["observation_mode"] = "forward_pit"
    out = ep.map_event(e, ep.xcals.get_calendar("XNYS"))
    assert out["available_at"] is None
    assert out["label_status"] == "missing_event_time"
def test_pit_missing_decision_is_rejected():
    e = event("2026-10-28T12:00:00Z")
    e["observation_mode"] = "forward_pit"
    e["first_seen_at_utc"] = "2026-10-28T14:00:00Z"
    out = ep.map_event(e, ep.xcals.get_calendar("XNYS"))
    assert out["entry_date"] is None
    assert out["label_status"] == "missing_decision_time"
    assert out["missing_reason"] == "missing_decision_at"


def test_decision_before_available_is_rejected():
    e = event("2026-10-28T12:00:00Z")
    e["observation_mode"] = "forward_pit"
    e["first_seen_at_utc"] = "2026-10-28T14:00:00Z"
    e["decision_at"] = "2026-10-28T13:00:00Z"
    out = ep.map_event(e, ep.xcals.get_calendar("XNYS"))
    assert out["entry_date"] is None
    assert out["label_status"] == "invalid_decision_time"
    assert out["missing_reason"] == "decision_before_available"


def test_retrospective_is_counterfactual():
    out = row("2026-10-28T12:00:00Z")
    assert out["plan_type"] == "retrospective_counterfactual"
    assert out["counterfactual"] is True
