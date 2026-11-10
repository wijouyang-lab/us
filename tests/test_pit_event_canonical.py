# -*- coding: utf-8 -*-
"""Tests for the strict PIT canonical event schema; no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import pit_event_canonical as mod  # noqa: E402


def base(**overrides):
    row = {
        "event_id": "e1", "event_type": "macro_release", "source": "bls",
        "source_url": "https://www.bls.gov/x", "published_at_utc": "2026-10-01T12:30:00Z",
        "first_seen_at_utc": "2026-10-01T12:31:00Z", "content_hash": "abc",
        "event_version_id": "v1", "supersedes_event_id": "e0",
        "event_time_utc": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_valid_record_keeps_event_time_separate_from_publication():
    out = mod.to_canonical(base())
    assert out["validation_status"] == "validated"
    assert out["event_time"] == "2026-09-01T00:00:00Z"
    assert out["source_published_at"] == "2026-10-01T12:30:00Z"
    assert out["first_seen_at"] == "2026-10-01T12:31:00Z"
    assert out["available_at"] == "2026-10-01T12:31:00Z"
    assert out["supersedes_event_id"] == "e0"
    assert out["revision_id"] == "v1"


def test_date_only_is_not_an_exact_timestamp():
    row = base(published_at_utc="2026-10-01")
    out = mod.to_canonical(row)
    assert out["timestamp_confidence"] == "date_only"
    assert out["validation_status"] == "rejected"
    assert "date_only_not_exact" in out["validation_reasons"]


def test_missing_source_url_cannot_validate():
    row = base(source_url="")
    out = mod.to_canonical(row)
    assert out["validation_status"] == "rejected"
    assert "missing_or_invalid_source_url" in out["validation_reasons"]


def test_available_at_never_precedes_first_seen():
    row = base(first_seen_at_utc="2026-10-01T12:31:00Z")
    row["update_first_seen_at_utc"] = "2026-10-01T12:20:00Z"
    out = mod.to_canonical(row)
    assert out["available_at"] >= out["first_seen_at"]


def test_source_quality_counts_are_per_source():
    events = [base(), base(event_id="e2", published_at_utc="2026-10-01"), base(event_id="e3", source="fed")]
    report = mod.source_quality_report(events)
    assert report["event_count"] == 3
    by = {s["source"]: s for s in report["sources"]}
    assert by["bls"]["events"] == 2
    assert by["bls"]["date_only"] == 1
    assert by["fed"]["events"] == 1
    assert report["not_alpha_evidence"] is True


def test_retraction_is_retained_but_not_validated():
    row = base(retracted_at_utc="2026-10-02T00:00:00Z")
    out = mod.to_canonical(row)
    assert out["retraction_status"] == "retracted"
    assert out["validation_status"] == "rejected"
    assert "retracted" in out["validation_reasons"]


def test_skipped_feed_appears_with_zero_success():
    metadata = {"source_reports": {"official_rss": {"feed_reports": [
        {"feed_key": "bls_cpi", "status": "skipped_missing_contact_user_agent",
         "error_type": "ContactUserAgentRequired"},
    ]}}}
    report = mod.source_quality_report([], metadata)
    row = next(s for s in report["sources"] if s["source"] == "bls_cpi_rss")
    assert row["events"] == 0
    assert row["capture_success_ratio"] == 0.0
    assert row["capture_failure_reasons"] == ["ContactUserAgentRequired"]


def test_capture_success_ratio_maps_feed_key_to_source():
    events = [base(source="bls_cpi_rss")]
    metadata = {"source_reports": {"official_rss": {"feed_reports": [
        {"feed_key": "bls_cpi", "status": "ok"},
    ]}}}
    report = mod.source_quality_report(events, metadata)
    by = {s["source"]: s for s in report["sources"]}
    assert by["bls_cpi_rss"]["capture_success_ratio"] == 1.0
