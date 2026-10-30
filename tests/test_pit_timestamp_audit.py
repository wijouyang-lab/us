# -*- coding: utf-8 -*-
"""Tests for SEC first-public and macro vintage separation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from pit_timestamp_audit import classify_sec, session_rule, split_vintage  # noqa: E402


def test_acceptance_is_not_first_public():
    out = classify_sec("2024-01-02T21:30:00Z", None, "2024-01-03T14:30:00Z")
    assert out["first_public_at"] is None
    assert out["timestamp_confidence"] == "unverified"
    assert out["pit_eligible"] is False


def test_verified_first_public_before_decision():
    ev = {"first_public_at": "2024-01-02T21:00:00Z", "source": "official-filing-index"}
    out = classify_sec("2024-01-02T21:30:00Z", ev, "2024-01-03T14:30:00Z")
    assert out["pit_eligible"] is True


def test_session_rules():
    assert session_rule("2024-01-02T13:00:00Z", trading_day=True) == "BEFORE_CLOSE"
    assert session_rule("2024-01-02T22:00:00Z", trading_day=True) == "AFTER_CLOSE"
    assert session_rule("2024-01-06T15:00:00Z", trading_day=False) == "NON_TRADING"


def test_vintage_keeps_first_and_revision():
    r = split_vintage("CPI", "2024-01-01", [
        {"realtime_start": "2024-01-01", "value": 100.0, "release_timestamp": "2024-01-15T13:30:00Z"},
        {"realtime_start": "2024-02-01", "value": 101.0, "release_timestamp": "2024-02-15T13:30:00Z"},
    ])
    assert r.first_release_value == 100.0
    assert r.revised_value == 101.0
    assert r.vintage_verified is True


def test_missing_vintage_not_verified():
    r = split_vintage("CPI", "2024-01-01", [{"realtime_start": None, "value": 100.0}])
    assert r.vintage_verified is False
    assert r.pit_eligible is False
