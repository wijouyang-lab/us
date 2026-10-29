# -*- coding: utf-8 -*-
"""Tests for event-to-daily-bar alignment; no network or strategy."""

import sys
from datetime import date
from pathlib import Path

from tools.research.pit_event_archive import event_version_id

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_market_alignment_audit as mod  # noqa: E402


def event(**overrides):
    row = {
        "event_id": "e1", "event_type": "policy", "source": "fed_test",
        "source_url": "https://www.federalreserve.gov/x",
        "published_at_utc": "2026-10-05T12:30:00Z",
        "first_seen_at_utc": "2026-10-05T12:31:00Z",
        "event_time_utc": "2026-10-05T12:30:00Z",
        "market_scope": "market",
        "tickers": [],
    }
    row.update(overrides)
    return row


DATES = [date(2026, 1, 15), date(2026, 1, 16), date(2026, 7, 1), date(2026, 7, 2),
         date(2026, 10, 2), date(2026, 10, 5), date(2026, 10, 6)]


def align(rows, decision="2026-10-05T21:00:00Z"):
    return mod.align_events(rows, DATES, decision_at=decision)


def test_premarket_event_uses_same_day_close():
    out = align([event()])
    row = out["events"][0]
    assert row["entry_bar_date"] == "2026-10-05"
    assert row["same_day_close_usable"] is True
    assert row["validation_status"] == "strict_pit"


def test_exact_close_and_after_close_use_next_session():
    exact = align([event(published_at_utc="2026-10-05T20:00:00Z", first_seen_at_utc="2026-10-05T20:01:00Z")])
    assert exact["events"][0]["entry_bar_date"] == "2026-10-06"
    after = align([event(published_at_utc="2026-10-05T20:30:00Z", first_seen_at_utc="2026-10-05T20:31:00Z")])
    assert after["events"][0]["entry_bar_date"] == "2026-10-06"


def test_weekend_event_uses_next_trading_day():
    out = align([event(published_at_utc="2026-10-03T14:00:00Z", first_seen_at_utc="2026-10-03T14:01:00Z")],
                decision="2026-10-05T21:00:00Z")
    assert out["events"][0]["entry_bar_date"] == "2026-10-05"


def test_dst_changes_close_instant():
    winter = align([event(published_at_utc="2026-01-15T21:00:00Z", first_seen_at_utc="2026-01-15T21:01:00Z")],
                   decision="2026-01-16T22:00:00Z")
    summer = align([event(published_at_utc="2026-07-01T20:00:00Z", first_seen_at_utc="2026-07-01T20:01:00Z")],
                   decision="2026-07-02T21:00:00Z")
    assert winter["events"][0]["entry_bar_date"] == "2026-01-16"
    assert summer["events"][0]["entry_bar_date"] == "2026-07-02"


def test_date_only_and_naive_timestamps_are_excluded():
    date_only = align([event(published_at_utc="2026-10-05")])
    assert date_only["events"][0]["validation_status"] == "excluded"
    naive = align([event(published_at_utc="2026-10-05T12:30:00")])
    assert naive["events"][0]["validation_status"] == "excluded"


def test_missing_event_time_is_descriptive_not_strict():
    out = align([event(event_time_utc=None)])
    row = out["events"][0]
    assert row["validation_status"] == "descriptive_only"
    assert "event_time_missing" in row["validation_reasons"]
    assert row["publication_forward_candidate"] is True


def test_revision_after_decision_is_not_used():
    v1 = event(first_seen_at_utc="2026-10-05T12:31:00Z")
    v1["event_version_id"] = event_version_id(v1)
    v2 = event(first_seen_at_utc="2026-10-06T12:31:00Z",
               published_at_utc="2026-10-06T12:30:00Z")
    v2["event_version_id"] = event_version_id(v2)
    out = mod.align_events([v1, v2], DATES, decision_at="2026-10-05T21:00:00Z")
    assert out["summary"]["selected_events"] == 1
    assert out["events"][0]["source_published_at"] == "2026-10-05T12:30:00Z"


def test_lookahead_flag_is_never_true():
    out = align([event()])
    assert out["summary"]["lookahead_flags"] == 0
    assert out["events"][0]["lookahead_flag"] is False
