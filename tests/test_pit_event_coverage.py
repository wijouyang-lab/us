from datetime import timedelta

from tools.research.pit_event_records import normalize_event
from tools.research.pit_event_coverage import audit_event_coverage


def test_coverage_audit_counts_missing_timestamps_and_eligible_events():
    good = normalize_event(
        "bls", "cpi-1", "macro_release",
        "2026-10-13T12:30:00Z", "2026-10-13T12:30:05Z",
    )
    missing = normalize_event(
        "sec_edgar", "filing-2", "company_news",
        None, "2026-10-13T12:30:05Z", tickers=["EXM"],
    )
    report = audit_event_coverage([good, missing], "2026-10-13T13:00:00Z")
    assert report["total_events"] == 2
    assert report["eligible_events"] == 1
    assert report["ineligible_events"] == 1
    assert report["availability_status_counts"]["timestamp_missing"] == 1
    assert report["audit_status"] == "fail_missing_data"
    assert report["audit_flags"] == ["fail_missing_data"]


def test_coverage_audit_flags_duplicate_event_ids():
    event = normalize_event(
        "bls", "cpi-1", "macro_release",
        "2026-10-13T12:30:00Z", "2026-10-13T12:30:05Z",
    )
    report = audit_event_coverage([event, event], "2026-10-13T13:00:00Z")
    assert report["duplicate_event_id_count"] == 1
    assert report["audit_status"] == "fail_duplicates"


def test_coverage_audit_rejects_unmapped_company_news_even_with_valid_times():
    event = normalize_event(
        "rss", "story-1", "company_news",
        "2026-10-13T12:30:00Z", "2026-10-13T12:30:05Z",
    )
    report = audit_event_coverage([event], "2026-10-13T13:00:00Z")
    assert report["eligible_events"] == 0
    assert report["audit_status"] == "fail_missing_data"


def test_coverage_audit_does_not_pass_if_available_flag_hides_missing_timestamp():
    event = {
        "event_id": "bad-missing-time",
        "event_type": "other",
        "availability_status": "available",
        "published_at_utc": None,
        "first_seen_at_utc": "2026-10-13T12:30:05Z",
    }
    report = audit_event_coverage([event], "2026-10-13T13:00:00Z")
    assert report["eligible_events"] == 0
    assert report["audit_status"] == "fail_missing_data"


def test_coverage_audit_flags_stale_events():
    event = normalize_event(
        "bls", "old-cpi", "macro_release",
        "2026-10-10T12:30:00Z", "2026-10-10T12:30:05Z",
    )
    report = audit_event_coverage(
        [event], "2026-10-13T13:00:00Z",
        max_age_by_type={"macro_release": timedelta(days=1)},
    )
    assert report["eligibility_reason_counts"] == {"stale_event": 1}
    assert report["audit_status"] == "fail_stale_events"


def test_empty_coverage_audit_is_deterministic():
    report = audit_event_coverage([], "2026-10-13T13:00:00Z")
    assert report["eligible_rate"] == 0.0
    assert report["total_events"] == 0
    assert report["audit_status"] == "pass"
    assert report["audit_flags"] == []
