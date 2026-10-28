import copy

import pytest

from tools.research.apply_event_annotations import apply_annotations
from tools.research.pit_event_archive import event_version_id


def archive_event():
    event = {
        "event_id": "event-1",
        "event_type": "macro_release",
        "source": "test_source",
        "source_event_id": "source-1",
        "published_at_utc": "2026-10-23T12:00:00Z",
        "first_seen_at_utc": "2026-10-23T12:01:00Z",
        "source_url": "https://example.test/event-1",
        "content_hash": "abc",
        "availability_status": "available",
    }
    event["event_version_id"] = event_version_id(event)
    return event


def reviewed_row(event, **overrides):
    row = {
        "event_version_id": event["event_version_id"],
        "direction_score": "0.5",
        "impact_score": "0.75",
        "label_review_status": "validated",
        "label_reviewed_at_utc": "2026-10-23T13:00:00Z",
        "label_rationale": "Source headline and official release context support a positive directional assessment.",
        "labeler_id": "analyst-1",
        "reviewer_id": "reviewer-2",
        "label_schema_version": "1.0",
    }
    row.update(overrides)
    return row


def test_apply_annotations_creates_derived_archive_without_mutating_source():
    event = archive_event()
    source = [copy.deepcopy(event)]
    output, report = apply_annotations(
        source,
        [reviewed_row(event), {"event_version_id": event["event_version_id"], "label_review_status": "pending"}],
        as_of="2026-10-23T14:00:00Z",
    )
    assert source[0].get("direction_score") is None
    assert output[0]["direction_score"] == 0.5
    assert output[0]["impact_score"] == 0.75
    assert output[0]["label_review_status"] == "validated"
    assert event_version_id(output[0]) == output[0]["event_version_id"]
    assert report["reviewed_annotations_applied"] == 1
    assert report["validated_annotations_applied"] == 1
    assert report["pending_rows_ignored"] == 1
    assert report["source_archive_overwritten"] is False
    assert report["labels_generated_by_tool"] is False


def test_apply_annotations_rejects_bad_scores_unknown_versions_and_duplicate_rows():
    event = archive_event()
    with pytest.raises(ValueError, match="direction_score must be finite"):
        apply_annotations([event], [reviewed_row(event, direction_score="2")], as_of="2026-10-23T14:00:00Z")
    with pytest.raises(ValueError, match="unknown event_version_id"):
        apply_annotations([event], [reviewed_row(event, event_version_id="unknown")], as_of="2026-10-23T14:00:00Z")
    with pytest.raises(ValueError, match="duplicate annotation"):
        apply_annotations([event], [reviewed_row(event), reviewed_row(event, label_review_status="reviewed")], as_of="2026-10-23T14:00:00Z")


def test_apply_annotations_requires_review_provenance_and_valid_timestamps():
    event = archive_event()
    with pytest.raises(ValueError, match="timezone-aware"):
        apply_annotations([event], [reviewed_row(event, label_reviewed_at_utc="2026-10-23T13:00:00")], as_of="2026-10-23T14:00:00Z")
    with pytest.raises(ValueError, match="after the import cutoff"):
        apply_annotations([event], [reviewed_row(event, label_reviewed_at_utc="2026-10-23T15:00:00Z")], as_of="2026-10-23T14:00:00Z")
    with pytest.raises(ValueError, match="distinct reviewer"):
        apply_annotations([event], [reviewed_row(event, labeler_id="analyst-1", reviewer_id="analyst-1")], as_of="2026-10-23T14:00:00Z")
    with pytest.raises(ValueError, match="not email addresses"):
        apply_annotations([event], [reviewed_row(event, labeler_id="analyst@example.com")], as_of="2026-10-23T14:00:00Z")



def test_apply_annotations_preserves_reviewed_ambiguous_scores_as_blank():
    event = archive_event()
    output, report = apply_annotations(
        [event],
        [reviewed_row(event, direction_score="", impact_score="", label_review_status="reviewed",
                      label_rationale="The source supports no defensible directional or impact score.")],
        as_of="2026-10-23T14:00:00Z",
    )
    assert output[0]["direction_score"] is None
    assert output[0]["impact_score"] is None
    assert output[0]["label_review_status"] == "reviewed"
    assert report["reviewed_annotations_applied"] == 1
    assert report["validated_annotations_applied"] == 0



def test_apply_annotations_imports_human_reviewed_mapping_without_mutating_source():
    event = archive_event()
    event.update({
        "event_type": "company_news",
        "source": "yahoo_finance_rss",
        "source_quality": "aggregator",
        "source_event_id": "AAPL|story-1",
        "tickers": ["AAPL"],
        "ticker_mapping_method": "per_ticker_yahoo_rss_query",
        "ticker_mapping_status": "unverified_query_scope",
        "ticker_mapping_confidence": "unverified",
    })
    event["event_version_id"] = event_version_id(event)
    source = [copy.deepcopy(event)]
    row = {
        "event_version_id": event["event_version_id"],
        "label_review_status": "pending",
        "mapping_review_status": "reviewed",
        "mapped_tickers_json": '["MSFT"]',
        "mapping_reviewed_at_utc": "2026-10-23T13:00:00Z",
        "mapping_reviewer_id": "mapping-reviewer-1",
        "mapping_rationale": "The headline directly concerns Microsoft, not the queried Apple symbol.",
        "mapping_schema_version": "1.0",
    }
    output, report = apply_annotations(source, [row], as_of="2026-10-23T14:00:00Z")
    assert source[0]["ticker_mapping_status"] == "unverified_query_scope"
    assert source[0]["tickers"] == ["AAPL"]
    assert output[0]["tickers"] == ["AAPL"]
    assert output[0]["ticker_mapping_review_status"] == "human_reviewed"
    assert output[0]["ticker_mapping_reviewed_tickers"] == ["MSFT"]
    assert output[0]["ticker_mapping_reviewer_id"] == "mapping-reviewer-1"
    assert event_version_id(output[0]) == output[0]["event_version_id"]
    assert report["reviewed_mappings_applied"] == 1
    assert report["reviewed_annotations_applied"] == 0
    assert report["mappings_inferred_by_tool"] is False


def test_apply_annotations_rejects_mapping_without_provenance_or_with_bad_tickers():
    event = archive_event()
    row = {
        "event_version_id": event["event_version_id"],
        "label_review_status": "pending",
        "mapping_review_status": "reviewed",
        "mapped_tickers_json": '["AAPL"]',
        "mapping_reviewed_at_utc": "2026-10-23T13:00:00Z",
        "mapping_reviewer_id": "mapping-reviewer-1",
        "mapping_rationale": "",
        "mapping_schema_version": "1.0",
    }
    with pytest.raises(ValueError, match="mapping rationale, reviewer and schema"):
        apply_annotations([event], [row], as_of="2026-10-23T14:00:00Z")
    row["mapping_rationale"] = "Explicitly reviewed headline relevance."
    row["mapped_tickers_json"] = '["BAD TICKER"]'
    with pytest.raises(ValueError, match="invalid reviewed ticker"):
        apply_annotations([event], [row], as_of="2026-10-23T14:00:00Z")


def test_apply_annotations_rejects_mapping_review_after_import_cutoff():
    event = archive_event()
    row = {
        "event_version_id": event["event_version_id"],
        "label_review_status": "pending",
        "mapping_review_status": "reviewed",
        "mapped_tickers_json": '[]',
        "mapping_reviewed_at_utc": "2026-10-23T15:00:00Z",
        "mapping_reviewer_id": "mapping-reviewer-1",
        "mapping_rationale": "Reviewed as unrelated to the queried ticker.",
        "mapping_schema_version": "1.0",
    }
    with pytest.raises(ValueError, match="after the import cutoff"):
        apply_annotations([event], [row], as_of="2026-10-23T14:00:00Z")
