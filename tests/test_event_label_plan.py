# -*- coding: utf-8 -*-
"""Tests for Fed event expected trading-date mapping; no prices/network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_label_plan as ep  # noqa: E402


def event(published="2026-10-28T14:00:00Z"):
    return {"event_id": "e1", "published_at_utc": published,
            "observation_mode": "retrospective_backfill"}


def row(published):
    out = ep.map_event(event(published), ep.xcals.get_calendar("XNYS"))
    return out


def test_premarket_and_intraday_use_same_session():
    assert row("2026-10-28T12:00:00Z")["entry_date"] == "2026-10-28"
    assert row("2026-10-28T18:00:00Z")["entry_date"] == "2026-10-28"


def test_after_close_uses_next_session():
    assert row("2026-10-28T21:00:00Z")["entry_date"] == "2026-10-29"


def test_weekend_uses_monday():
    assert row("2026-10-31T12:00:00Z")["entry_date"] == "2026-11-02"


def test_holiday_and_early_close():
    assert row("2026-11-26T12:00:00Z")["entry_date"] == "2026-11-27"
    # 2026-11-27 is an early close (18:00 UTC); after it -> Monday.
    assert row("2026-11-27T19:00:00Z")["entry_date"] == "2026-11-30"


def test_plus1_and_plus5_are_sessions():
    out = row("2026-10-28T14:00:00Z")
    assert out["plus1_date"] == "2026-10-29"
    assert out["plus5_date"] == "2026-11-04"


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
