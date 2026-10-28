# -*- coding: utf-8 -*-
"""Tests for the persistent cross-run event archive."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_archive_store as store  # noqa: E402
from tools.research.pit_event_records import normalize_event  # noqa: E402


def _event(first_seen="2026-10-20T12:01:00Z", *, payload="initial"):
    return normalize_event(
        source="fed_test", source_event_id="e1", event_type="policy",
        published_at_utc="2026-10-20T12:00:00Z", first_seen_at_utc=first_seen,
        raw_payload={"headline": payload},
    )


def _snapshot(root: Path, events, name="run"):
    d = root / name
    d.mkdir(parents=True)
    (d / "events.json").write_text(json.dumps(events), encoding="utf-8")
    (d / "metadata.json").write_text(json.dumps({"event_count": len(events), "source_reports": {}}), encoding="utf-8")
    (d / "audit.json").write_text(json.dumps({"coverage_audit": {"audit_status": "pass"}}), encoding="utf-8")
    return d


def test_two_runs_add_observations_not_new_events(tmp_path):
    first = store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [_event()], "r1"), run_id="1")
    second = store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [_event("2026-10-21T12:01:00Z")], "r2"), run_id="2")
    assert first["counts"]["new_events"] == 1
    assert second["counts"]["new_events"] == 0
    assert second["counts"]["new_versions"] == 0
    assert second["counts"]["duplicate_observations"] == 1
    assert second["counts"]["observations"] == 2


def test_reimport_same_run_is_idempotent(tmp_path):
    snap = _snapshot(tmp_path, [_event()], "r1")
    store.import_snapshot(tmp_path / "store", snap, run_id="1")
    second = store.import_snapshot(tmp_path / "store", snap, run_id="1")
    assert second["counts"]["observations"] == 1
    assert second["counts"]["new_observations"] == 0


def test_changed_content_creates_version_and_supersedes(tmp_path):
    store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [_event()], "r1"), run_id="1")
    second = store.import_snapshot(
        tmp_path / "store", _snapshot(tmp_path, [_event("2026-10-21T12:01:00Z", payload="revised")], "r2"), run_id="2")
    assert second["counts"]["revisions"] == 1
    assert second["counts"]["new_versions"] == 1
    archive = json.loads((tmp_path / "store/archive/event_archive.json").read_text())
    assert len(archive) == 2
    versions = sorted(archive, key=lambda x: x["first_seen_at_utc"])
    assert versions[1]["supersedes_event_version_id"] == versions[0]["event_version_id"]


def test_retraction_is_retained(tmp_path):
    event = _event()
    event["retracted_at_utc"] = "2026-10-22T00:00:00Z"
    result = store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [event], "r1"), run_id="1")
    assert result["counts"]["retractions"] == 1
    archive = json.loads((tmp_path / "store/archive/event_archive.json").read_text())
    assert len(archive) == 1


def test_corrupt_archive_fails_without_overwrite(tmp_path):
    root = tmp_path / "store"
    (root / "archive").mkdir(parents=True)
    bad = root / "archive/event_archive.json"
    bad.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        store.import_snapshot(root, _snapshot(tmp_path, [_event()], "r1"), run_id="1")
    assert bad.read_text(encoding="utf-8") == "{not-json"


def test_conflicting_published_timestamps_are_counted(tmp_path):
    store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [_event()], "r1"), run_id="1")
    shifted = _event("2026-10-21T12:01:00Z", payload="revised")
    shifted["published_at_utc"] = "2026-10-20T13:00:00Z"
    result = store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [shifted], "r2"), run_id="2")
    assert result["counts"]["timestamp_conflicts"] == 1


def test_missing_snapshot_and_hash_mismatch_fail(tmp_path):
    store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [_event()], "r1"), run_id="1")
    events = tmp_path / "store/runs/1/events.json"
    original = events.read_text(encoding="utf-8")
    events.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        store.rebuild(tmp_path / "store")
    events.write_text(original, encoding="utf-8")
    events.unlink()
    with pytest.raises(ValueError, match="missing events"):
        store.rebuild(tmp_path / "store")


def test_missing_latest_manifest_and_observations_fail(tmp_path):
    store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [_event()], "r1"), run_id="1")
    (tmp_path / "store/archive/latest_manifest.json").unlink()
    with pytest.raises(ValueError, match="latest_manifest"):
        store.rebuild(tmp_path / "store")


def test_rebuild_matches_archive(tmp_path):
    store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [_event()], "r1"), run_id="1")
    store.import_snapshot(tmp_path / "store", _snapshot(tmp_path, [_event("2026-10-21T12:01:00Z")], "r2"), run_id="2")
    result = store.rebuild(tmp_path / "store")
    assert result["reproducible"] is True
    assert result["unique_event_ids"] == 1
    assert result["versions"] == 1
