from datetime import timedelta

from tools.research.pit_event_records import normalize_event
from tools.research.pit_event_research_pipeline import build_event_research_report


def test_pipeline_report_is_deterministic_and_input_order_independent():
    macro = normalize_event(
        "bls", "cpi-2026-09", "macro_release",
        "2026-10-15T12:30:00Z", "2026-10-15T12:30:05Z",
        raw_payload={"series": "CPI", "value": 3.1},
    )
    macro.update({
        "actual_value": 3.1,
        "consensus_value": 3.0,
        "consensus_asof_utc": "2026-10-15T12:00:00Z",
    })
    news = normalize_event(
        "sec_edgar", "filing-1", "company_news",
        "2026-10-15T11:00:00Z", "2026-10-15T11:00:05Z",
        tickers=["EXM"],
    )
    decision_at = "2026-10-15T12:31:00Z"
    one = build_event_research_report(
        [macro, news], decision_at,
        max_age_by_type={"macro_release": timedelta(days=1)},
    )
    two = build_event_research_report(
        [news, macro], decision_at,
        max_age_by_type={"macro_release": timedelta(days=1)},
    )
    assert one == two
    assert len(one["input_snapshot_sha256"]) == 64
    assert one["coverage_audit"]["eligible_events"] == 2
    assert one["macro_surprise"]["eligible_count"] == 1
    assert one["trading_signal_generated"] is False


def test_pipeline_exposes_missing_consensus_instead_of_filling_zero():
    macro = normalize_event(
        "bls", "cpi-2026-10", "macro_release",
        "2026-10-15T12:30:00Z", "2026-10-15T12:30:05Z",
    )
    macro["actual_value"] = 3.2
    macro["consensus_value"] = 3.1
    macro["consensus_asof_utc"] = None
    report = build_event_research_report([macro], "2026-10-15T12:31:00Z")
    summary = report["macro_surprise"]
    assert summary["eligible_count"] == 0
    assert summary["ineligible_count"] == 1
    assert summary["reason_counts"] == {"consensus_timestamp_missing": 1}
    assert summary["records"][0]["surprise"] is None


def test_pipeline_hash_changes_when_event_payload_changes():
    original = normalize_event(
        "rss", "story-1", "other", "2026-10-15T10:00:00Z",
        "2026-10-15T10:01:00Z", raw_payload={"headline": "First version"},
    )
    changed = dict(original, content_hash="different-content-hash")
    a = build_event_research_report([original], "2026-10-15T12:00:00Z")
    b = build_event_research_report([changed], "2026-10-15T12:00:00Z")
    assert a["input_snapshot_sha256"] != b["input_snapshot_sha256"]


def test_pipeline_handles_empty_data_as_zero_coverage_not_alpha():
    report = build_event_research_report([], "2026-10-15T12:00:00Z")
    assert report["input_event_count"] == 0
    assert report["coverage_audit"]["eligible_rate"] == 0.0
    assert report["macro_surprise"]["candidate_count"] == 0
    assert report["research_only"] is True
