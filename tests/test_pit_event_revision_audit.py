# -*- coding: utf-8 -*-
"""Tests for multi-snapshot event revision audit."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import pit_event_revision_audit as mod  # noqa: E402


def _event(event_id="e1", version="v1", published="2026-10-01T12:00:00Z",
           first_seen="2026-10-01T12:01:00Z"):
    return {"event_id": event_id, "event_version_id": version, "source": "src",
            "published_at_utc": published, "first_seen_at_utc": first_seen}


def test_duplicate_and_revision_are_counted_separately(tmp_path):
    snap1 = tmp_path / "a.events.json"
    snap2 = tmp_path / "b.events.json"
    archive = tmp_path / "archive.json"
    snap1.write_text(json.dumps([_event()]), encoding="utf-8")
    snap2.write_text(json.dumps([_event(first_seen="2026-10-02T12:01:00Z")]), encoding="utf-8")
    (tmp_path / "c").mkdir(exist_ok=True)
    archive.write_text(json.dumps([_event()]), encoding="utf-8")
    out = mod.audit([snap1, snap2], archive)
    src = out["sources"][0]
    assert src["observations"] == 2
    assert src["version_count"] == 1
    assert src["duplicate_observations"] == 1
    assert src["revision_count"] == 0
    assert src["first_observed_at"] == "2026-10-01T12:01:00Z"
    assert src["last_observed_at"] == "2026-10-02T12:01:00Z"


def test_changed_timestamp_is_a_conflict(tmp_path):
    snap = tmp_path / "a.events.json"
    archive = tmp_path / "archive.json"
    snap.write_text(json.dumps([
        _event(published="2026-10-01T12:00:00Z", version="v1"),
        _event(published="2026-10-01T13:00:00Z", version="v2"),
    ]), encoding="utf-8")
    archive.write_text(json.dumps([_event()]), encoding="utf-8")
    out = mod.audit([snap], archive)
    assert out["sources"][0]["timestamp_conflict_count"] == 1
