# -*- coding: utf-8 -*-
"""Tests for PIT/retrospective event dataset separation; no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_research_dataset as ds  # noqa: E402


def event(mode=None, first="2026-10-28T09:00:00Z", published="2026-10-01T15:00:00Z", **kw):
    d = {"event_id": "e1", "event_type": "policy", "source": "fed",
         "source_url": "https://example.test/e1", "content_hash": "a" * 64,
         "published_at_utc": published, "first_seen_at_utc": first,
         "availability_status": "available"}
    if mode:
        d["observation_mode"] = mode
    d.update(kw)
    return d


def label(**kw):
    d = {"status": "pending_future_entry_bar", "entry_bar_date": "2026-10-28",
         "result_1d_date": None, "result_5d_date": None}
    d.update(kw)
    return {"e1": d}


def test_forward_pit_uses_first_seen_and_keeps_missing_labels():
    out = ds.build([event()], label(), "forward_pit")
    row = out["rows"][0]
    assert row["observation_mode"] == "forward_pit"
    assert row["pit_eligible"] is True
    assert row["available_at"] == "2026-10-28T09:00:00Z"
    assert row["result_1d_date"] is None
    assert row["result_5d_date"] is None


def test_retrospective_requires_backfill_source_and_is_not_pit():
    out = ds.build([event("retrospective_backfill")], label(), "forward_pit")
    row = out["rows"][0]
    assert row["observation_mode"] == "unknown"
    assert row["pit_eligible"] is False
    assert row["backfill_status"] == "retrospective"


def test_missing_timestamps_fail_closed():
    out = ds.build([event(published=None)], label(), "forward_pit")
    row = out["rows"][0]
    assert row["available_at"] == "2026-10-28T09:00:00Z"
    assert row["published_at"] is None
    assert row["pit_eligible"] is False  # publication missing -> fail closed


def test_all_missing_timestamps_are_not_pit():
    e = event(published=None, first=None)
    out = ds.build([e], label(), "forward_pit")
    assert out["rows"][0]["pit_eligible"] is False


def test_missing_readiness_label_is_not_zero_filled():
    out = ds.build([event()], {}, "forward_pit")
    row = out["rows"][0]
    assert row["entry_bar_date"] is None
    assert row["result_1d_date"] is None
    assert row["label_status"] == "missing_label"
    assert row["missing_reason"] == "no_readiness_label"
