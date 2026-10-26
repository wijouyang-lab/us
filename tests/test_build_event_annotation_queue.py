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



def test_annotation_queue_uses_earliest_version_and_caps_a_balanced_queue():
    story_first = event(
        "story", "2026-10-25T12:00:00Z", "2026-10-25T12:01:00Z",
        event_type="company_news", source="yahoo_finance_rss",
        source_quality="aggregator", source_event_id="AAPL|story-1",
        tickers=["AAPL"], ticker_mapping_method="per_ticker_yahoo_rss_query",
        ticker_mapping_status="unverified_query_scope",
        ticker_mapping_confidence="unverified",
    )
    story_first["event_version_id"] = "story-v1"
    story_revision = dict(story_first)
    story_revision.update(
        event_version_id="story-v2",
        first_seen_at_utc="2026-10-25T12:05:00Z",
        headline="Corrected story title",
    )
    macro = event(
        "macro", "2026-10-25T11:00:00Z", "2026-10-25T11:01:00Z",
        event_type="macro_release", source="bea_news_release_rss",
    )
    policy = event(
        "policy", "2026-10-25T10:00:00Z", "2026-10-25T10:01:00Z",
        event_type="policy", source="federal_reserve_press_rss",
    )
    queue, report = build_annotation_queue(
        [story_first, story_revision, macro, policy],
        as_of="2026-10-26T12:00:00Z",
        max_age_days=30,
        max_rows=2,
    )
    assert len(queue) == 2
    assert {row["event_id"] for row in queue} == {"story", "macro"}
    story_row = next(row for row in queue if row["event_id"] == "story")
    assert story_row["event_version_id"] == "story-v1"
    assert story_row["headline"] == "Test event"
    assert story_row["queried_ticker"] == "AAPL"
    assert story_row["ticker_mapping_status"] == "unverified_query_scope"
    assert story_row["mapping_review_status"] == "pending"
    assert story_row["mapped_tickers_json"] == '["AAPL"]'
    assert story_row["label_review_status"] == "pending"
    assert story_row["direction_score"] == ""
    assert report["eligible_candidate_count"] == 3
    assert report["queue_rows"] == 2
    assert report["deferred_rows"] == 1
    assert report["deduplicated_later_versions"] == 1


def test_annotation_queue_fails_closed_for_ambiguous_first_observation():
    first = event(
        "ambiguous", "2026-10-25T12:00:00Z", "2026-10-25T12:01:00Z",
    )
    second = dict(first, event_version_id="other-version", headline="other content")
    queue, report = build_annotation_queue(
        [first, second], as_of="2026-10-26T12:00:00Z", max_rows=10
    )
    assert queue == []
    assert report["excluded_counts"]["ambiguous_first_seen"] == 1
