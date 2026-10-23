from __future__ import annotations

import json

import pandas as pd
import pytest

from tools.research.audit_pit_event_data_readiness import audit_event_archive


def event(**updates):
    row = {
        "event_id": "event-1",
        "event_version_id": "version-1",
        "source": "official_test_feed",
        "source_url": "https://example.test/event-1",
        "source_event_id": "source-1",
        "event_type": "macro_release",
        "availability_status": "available",
        "published_at_utc": "2026-01-02T12:00:00Z",
        "first_seen_at_utc": "2026-01-02T12:01:00Z",
        "source_quality": "official",
        "content_hash": "hash-1",
        "direction_score": 0.5,
        "impact_score": 0.8,
        "label_review_status": "reviewed",
        "label_reviewed_at_utc": "2026-01-02T12:02:00Z",
    }
    row.update(updates)
    return row


def test_audit_reports_label_timestamp_and_pit_readiness(tmp_path):
    archive = tmp_path / "archive.json"
    decisions = tmp_path / "decisions.csv"
    archive.write_text(json.dumps([event()]), encoding="utf-8")
    pd.DataFrame([{"decision_at": "2026-01-03T12:00:00Z"}]).to_csv(decisions, index=False)

    result = audit_event_archive(
        archive, decisions_path=decisions, audited_at="2026-01-04T00:00:00Z"
    )

    assert result["status"] == "review_required"
    assert result["archive_event_version_rows"] == 1
    assert result["event_families"] == {"macro_release": 1}
    assert result["label_quality"]["fully_labeled_fraction"] == 1.0
    assert result["pit_eligibility"]["eligible_events_by_decision"]["2026-01-03T12:00:00Z"] == 1
    assert result["readiness_gates"]["empirical_alpha_established"] is False
    assert result["readiness_gates"]["production_activation_allowed"] is False


def test_audit_flags_missing_labels_and_timestamp_quality(tmp_path):
    archive = tmp_path / "archive.json"
    archive.write_text(json.dumps([
        event(direction_score=None, first_seen_at_utc="2026-01-02T11:00:00Z"),
        event(event_id="event-2", event_version_id="version-1", direction_score=2.0),
    ]), encoding="utf-8")

    result = audit_event_archive(archive, audited_at="2026-01-04T00:00:00Z")

    assert result["status"] == "blocked_no_validated_labels"
    assert result["duplicate_event_version_id_count"] == 1
    assert result["timestamp_quality"]["first_seen_before_publication"] == 1
    assert result["label_quality"]["fully_labeled_fraction"] == 0.0



def test_audit_blocks_archive_without_source_urls(tmp_path):
    archive = tmp_path / "archive.json"
    row = event()
    row.pop("source_url")
    archive.write_text(json.dumps([row]), encoding="utf-8")

    result = audit_event_archive(archive, audited_at="2026-01-04T00:00:00Z")

    assert result["status"] == "blocked_data_quality"
    assert result["missing_required_fields"]["source_url"] == 1
    assert result["readiness_gates"]["source_urls_present"] is False

def test_audit_blocks_malformed_source_urls(tmp_path):
    archive = tmp_path / "archive.json"
    archive.write_text(json.dumps([event(source_url="javascript:alert(1)")]), encoding="utf-8")

    result = audit_event_archive(archive, audited_at="2026-01-04T00:00:00Z")

    assert result["status"] == "blocked_data_quality"
    assert result["timestamp_quality"]["invalid_source_url"] == 1
    assert result["readiness_gates"]["source_urls_valid_https"] is False


def test_audit_blocks_future_event_timestamps(tmp_path):
    archive = tmp_path / "archive.json"
    archive.write_text(json.dumps([event(first_seen_at_utc="2026-01-05T00:00:00Z")]), encoding="utf-8")

    result = audit_event_archive(archive, audited_at="2026-01-04T00:00:00Z")

    assert result["status"] == "blocked_data_quality"
    assert result["timestamp_quality"]["first_seen_after_audit_time"] == 1
    assert result["readiness_gates"]["all_timestamps_valid_and_not_future"] is False


def test_audit_does_not_treat_unreviewed_numeric_labels_as_validated(tmp_path):
    archive = tmp_path / "archive.json"
    archive.write_text(
        json.dumps([event(label_review_status="pending", label_reviewed_at_utc=None)]),
        encoding="utf-8",
    )

    result = audit_event_archive(archive, audited_at="2026-01-04T00:00:00Z")

    assert result["status"] == "blocked_no_validated_labels"
    assert result["label_quality"]["fully_labeled_fraction"] == 1.0
    assert result["label_quality"]["reviewed_label_fraction"] == 0.0
    assert result["readiness_gates"]["validated_labels_present"] is False


def test_audit_rejects_naive_decision_timestamps(tmp_path):
    archive = tmp_path / "archive.json"
    decisions = tmp_path / "decisions.csv"
    archive.write_text("[]", encoding="utf-8")
    pd.DataFrame([{"decision_at": "2026-01-03T12:00:00"}]).to_csv(decisions, index=False)

    with pytest.raises(ValueError, match="timezone-aware"):
        audit_event_archive(archive, decisions_path=decisions)


def test_audit_marks_empty_archive_as_no_data(tmp_path):
    archive = tmp_path / "archive.json"
    archive.write_text("[]", encoding="utf-8")

    result = audit_event_archive(archive, audited_at="2026-01-04T00:00:00Z")

    assert result["status"] == "fail_no_data"
    assert result["readiness_gates"]["archive_nonempty"] is False



def test_audit_reports_recoverable_official_url_without_hiding_it(tmp_path):
    archive = tmp_path / "archive.json"
    row = event(source_url="www.bea.gov/news/2026/release")
    archive.write_text(json.dumps([row]), encoding="utf-8")
    result = audit_event_archive(str(archive), audited_at="2026-10-23T13:00:00Z")
    assert result["timestamp_quality"]["canonicalizable_source_url"] == 1
    assert result["timestamp_quality"].get("invalid_source_url", 0) == 0
    assert result["canonicalizable_source_urls"][0]["canonical_source_url"] == "https://www.bea.gov/news/2026/release"
    assert result["readiness_gates"]["source_urls_valid_https"] is False
    assert result["readiness_gates"]["source_urls_valid_or_canonicalizable"] is True
