import pytest

from tools.research.build_event_annotation_queue import build_annotation_queue


def event(event_id, published, first_seen, **extra):
    row = {
        "event_id": event_id,
        "event_version_id": event_id + "-v1",
        "event_type": "macro_release",
        "headline": "Test event",
        "source": "official_test",
        "source_url": "https://example.gov/event",
        "published_at_utc": published,
        "first_seen_at_utc": first_seen,
        "content_hash": "abc",
        "market_scope": "market",
        "tickers": [],
        "sectors": [],
    }
    row.update(extra)
    return row


def test_annotation_queue_keeps_only_recent_asof_unreviewed_events():
    archive = [
        event("recent", "2026-10-22T12:00:00Z", "2026-10-22T12:01:00Z"),
        event("old", "2026-08-01T12:00:00Z", "2026-08-01T12:01:00Z"),
        event("future", "2026-10-25T12:00:00Z", "2026-10-25T12:01:00Z"),
        event("reviewed", "2026-10-22T12:00:00Z", "2026-10-22T12:01:00Z", label_review_status="reviewed"),
        event("invalid", "2026-10-22T12:00:00", "2026-10-22T12:01:00Z"),
    ]
    queue, report = build_annotation_queue(archive, as_of="2026-10-23T16:00:00Z", max_age_days=30)
    assert [row["event_id"] for row in queue] == ["recent"]
    assert queue[0]["direction_score"] == ""
    assert queue[0]["impact_score"] == ""
    assert queue[0]["label_review_status"] == "pending"
    assert queue[0]["label_reviewed_at_utc"] == ""
    assert report["labels_generated"] is False
    assert report["excluded_counts"]["stale"] == 1
    assert report["excluded_counts"]["not_yet_available"] == 1
    assert report["excluded_counts"]["already_reviewed"] == 1
    assert report["excluded_counts"]["invalid_timestamps"] == 1


def test_annotation_queue_rejects_naive_cutoff_and_negative_age():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_annotation_queue([], as_of="2026-10-23T16:00:00")
    with pytest.raises(ValueError, match="non-negative"):
        build_annotation_queue([], as_of="2026-10-23T16:00:00Z", max_age_days=-1)
