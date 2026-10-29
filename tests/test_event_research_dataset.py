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


def ev(**kw):
    d = {"run_id": "run1", "captured_at": "2026-10-28T09:02:58Z",
         "events_sha256": "b" * 64, "snapshot": "runs/run1/events.json"}
    d.update(kw)
    return {"e1": d}


def label(**kw):
    d = {"status": "pending_future_entry_bar", "entry_bar_date": "2026-10-28",
         "result_1d_date": None, "result_5d_date": None}
    d.update(kw)
    return {"e1": d}


def test_forward_pit_requires_capture_evidence_and_separates_labels():
    out = ds.build([event()], label(), "forward_pit", ev())
    row = out["rows"][0]
    assert row["observation_mode"] == "forward_pit"
    assert row["pit_eligible"] is True
    assert row["available_at"] == "2026-10-28T09:00:00Z"
    assert row["has_entry"] is True
    assert row["has_plus1"] is False
    assert row["has_plus5"] is False
    assert row["pit_reasons"] == []


def test_forward_pit_without_evidence_is_unknown():
    out = ds.build([event()], label(), "forward_pit")
    row = out["rows"][0]
    assert row["observation_mode"] == "unknown"
    assert row["pit_eligible"] is False
    assert "missing_capture_evidence" in row["pit_reasons"]


def test_first_seen_before_published_is_ineligible():
    out = ds.build([event(published="2026-10-29T00:00:00Z")], label(), "forward_pit", ev())
    assert out["rows"][0]["pit_eligible"] is False
    assert "first_seen_before_published" in out["rows"][0]["pit_reasons"]


def test_first_seen_after_capture_record_is_ineligible():
    out = ds.build([event(first="2026-10-28T09:05:00Z")], label(), "forward_pit", ev())
    assert out["rows"][0]["pit_eligible"] is False
    assert "first_seen_after_capture_record" in out["rows"][0]["pit_reasons"]


def test_retrospective_requires_backfill_source_and_is_not_pit():
    out = ds.build([event("retrospective_backfill")], label(), "forward_pit", ev())
    row = out["rows"][0]
    assert row["observation_mode"] == "unknown"
    assert row["pit_eligible"] is False
    assert row["backfill_status"] == "retrospective"

    out = ds.build([event("retrospective_backfill", backfill_source="fed-archive")],
                   label(), "forward_pit", ev())
    assert out["rows"][0]["observation_mode"] == "retrospective_backfill"
    assert out["rows"][0]["pit_eligible"] is False


def test_missing_labels_are_not_zero_filled():
    out = ds.build([event()], {}, "forward_pit", ev())
    row = out["rows"][0]
    assert row["has_entry"] is False
    assert row["entry_bar_date"] is None
    assert row["label_status"] == "missing_label"
    assert row["missing_reason"] == "no_readiness_label"
