import json

import pytest

from tools.research.pit_event_archive import (
    append_archive_file,
    event_version_id,
    merge_event_archive,
    select_event_versions_asof,
)
from tools.research.pit_event_records import normalize_event


def make_event(first_seen, *, raw_payload=None, status="available", published="2026-10-20T12:00:00Z"):
    row = normalize_event(
        source="sec_edgar",
        source_event_id="accession-1",
        event_type="company_news",
        published_at_utc=published,
        first_seen_at_utc=first_seen,
        tickers=["EXM"],
        raw_payload=raw_payload or {"form": "8-K", "headline": "Initial"},
    )
    if status != "available":
        row["availability_status"] = status
    row["source_header_sha256"] = "head-a"
    return row


def test_archive_deduplicates_same_version_and_preserves_earliest_first_seen():
    first = make_event("2026-10-21T12:00:00Z")
    later_observation = dict(first, first_seen_at_utc="2026-10-22T12:00:00Z")
    archive, report = merge_event_archive([], [first, later_observation])
    assert len(archive) == 1
    assert report["new_version_count"] == 1
    assert report["duplicate_version_count"] == 1
    assert archive[0]["first_seen_at_utc"] == "2026-10-21T12:00:00Z"
    assert archive[0]["event_version_id"] == event_version_id(archive[0])


def test_archive_preserves_changed_source_versions_and_selects_asof():
    v1 = make_event(
        "2026-10-21T12:00:00Z",
        raw_payload={"form": "8-K", "headline": "Initial"},
    )
    v2 = make_event(
        "2026-10-23T12:00:00Z",
        raw_payload={"form": "8-K", "headline": "Corrected"},
    )
    archive, report = merge_event_archive([], [v1, v2])
    assert len(archive) == 2
    assert report["new_version_count"] == 2
    assert len({x["event_version_id"] for x in archive}) == 2

    early = select_event_versions_asof(archive, "2026-10-22T12:00:00Z")
    late = select_event_versions_asof(archive, "2026-10-24T12:00:00Z")
    assert len(early) == 1
    assert early[0]["content_hash"] == v1["content_hash"]
    assert len(late) == 1
    assert late[0]["content_hash"] == v2["content_hash"]


def test_archive_ignores_transient_fetch_error_records():
    valid = make_event("2026-10-21T12:00:00Z")
    failed = make_event(
        "2026-10-22T12:00:00Z",
        raw_payload={"form": "8-K", "headline": "broken fetch"},
        status="fetch_error",
        published=None,
    )
    archive, report = merge_event_archive([], [valid, failed])
    assert len(archive) == 1
    assert report["fetch_error_skipped_count"] == 1
    selected = select_event_versions_asof([valid, failed], "2026-10-23T00:00:00Z")
    assert len(selected) == 1
    assert selected[0]["event_id"] == valid["event_id"]


def test_archive_rejects_missing_first_seen_and_tampered_version_ids():
    event = make_event("2026-10-21T12:00:00Z")
    with pytest.raises(ValueError, match="first_seen_at_utc"):
        merge_event_archive([], [dict(event, first_seen_at_utc=None)])
    with pytest.raises(ValueError, match="does not match archived content"):
        merge_event_archive([dict(event, event_version_id="wrong")], [])


def test_archive_file_append_is_idempotent_and_refuses_same_input_path(tmp_path):
    source = tmp_path / "capture.json"
    archive_file = tmp_path / "events.archive.json"
    event = make_event("2026-10-21T12:00:00Z")
    source.write_text(json.dumps([event]), encoding="utf-8")

    first = append_archive_file(source, archive_file)
    second = append_archive_file(source, archive_file)
    contents = json.loads(archive_file.read_text(encoding="utf-8"))
    assert first["new_version_count"] == 1
    assert second["new_version_count"] == 0
    assert second["duplicate_version_count"] == 1
    assert len(contents) == 1
    assert len(second["archive_snapshot_sha256"]) == 64

    with pytest.raises(ValueError, match="must be different files"):
        append_archive_file(source, source)


def test_archive_rejects_non_timezone_aware_decision_for_asof_selection():
    event = make_event("2026-10-21T12:00:00Z")
    with pytest.raises(ValueError, match="timezone-aware"):
        select_event_versions_asof([event], "2026-10-22T12:00:00")
