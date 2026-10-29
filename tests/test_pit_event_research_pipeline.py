from datetime import datetime, timedelta

from tools.research.pit_event_archive import merge_event_archive
from tools.research.pit_event_records import normalize_event as _normalize_event

EVIDENCE = {
    "parse_status": "exact",
    "source_evidence": "official_fed_page",
    "published_at_evidence": "official_release_time_in_page",
    "decision_evidence": "strategy_log",
    "is_simulated": False,
    "observation_kind": "live_forward_observation",
}


def normalize_event(*args, **kwargs):
    event = _normalize_event(*args, **kwargs)
    event.update(EVIDENCE)
    event["research_ready_at_utc"] = event.get("first_seen_at_utc")
    first = event.get("first_seen_at_utc") or ""
    if first:
        event["decision_at_utc"] = (
            datetime.fromisoformat(first.replace("Z", "+00:00")) + timedelta(minutes=5)
        ).isoformat().replace("+00:00", "Z")
    return event
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
    macro_2 = normalize_event(
        "bls", "cpi-2026-08", "macro_release",
        "2026-10-15T12:29:00Z", "2026-10-15T12:29:05Z",
        raw_payload={"series": "CPI", "value": 3.0},
    )
    macro_2.update({
        "actual_value": 3.0,
        "consensus_value": 2.9,
        "consensus_asof_utc": "2026-10-15T12:10:00Z",
    })
    news = normalize_event(
        "sec_edgar", "filing-1", "company_news",
        "2026-10-15T11:00:00Z", "2026-10-15T11:00:05Z",
        tickers=["EXM"],
    )
    decision_at = "2026-10-15T12:31:00Z"
    one = build_event_research_report(
        [macro, news, macro_2], decision_at,
        max_age_by_type={"macro_release": timedelta(days=1)},
    )
    two = build_event_research_report(
        [macro_2, news, macro], decision_at,
        max_age_by_type={"macro_release": timedelta(days=1)},
    )
    assert one == two
    assert len(one["input_snapshot_sha256"]) == 64
    assert one["coverage_audit"]["eligible_events"] == 3
    assert one["macro_surprise"]["eligible_count"] == 2
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


def test_pipeline_uses_latest_archive_version_available_by_decision_time():
    older = normalize_event(
        "sec_edgar", "filing-2", "company_news",
        "2026-10-20T10:00:00Z", "2026-10-21T10:00:00Z",
        tickers=["EXM"], raw_payload={"headline": "Original"},
    )
    newer = normalize_event(
        "sec_edgar", "filing-2", "company_news",
        "2026-10-20T10:00:00Z", "2026-10-23T10:00:00Z",
        tickers=["EXM"], raw_payload={"headline": "Revised"},
    )
    archive, _ = merge_event_archive([], [older, newer])

    early = build_event_research_report(archive, "2026-10-22T12:00:00Z")
    late = build_event_research_report(archive, "2026-10-24T12:00:00Z")
    assert early["asof_selection_applied"] is True
    assert early["input_event_count"] == 2
    assert early["asof_event_count"] == 1
    assert late["asof_event_count"] == 1
    assert early["input_snapshot_sha256"] != late["input_snapshot_sha256"]
    assert early["coverage_audit"]["eligible_events"] == 0
    assert late["coverage_audit"]["eligible_events"] == 0


def test_pipeline_rejects_mixed_versioned_and_unversioned_input():
    event = normalize_event(
        "rss", "story-3", "other", "2026-10-15T10:00:00Z",
        "2026-10-15T10:01:00Z",
    )
    versioned = dict(event, event_version_id="made-up")
    import pytest

    with pytest.raises(ValueError, match="cannot mix"):
        build_event_research_report([event, versioned], "2026-10-15T12:00:00Z")



def test_pipeline_propagates_expected_source_coverage_contract():
    event = normalize_event(
        "bls_cpi_rss", "cpi-1", "macro_release",
        "2026-10-15T12:30:00Z", "2026-10-15T12:30:05Z",
    )
    report = build_event_research_report(
        [event],
        "2026-10-15T12:31:00Z",
        expected_sources=["bls_cpi_rss", "federal_reserve_press_rss"],
    )
    assert report["coverage_audit"]["missing_sources"] == ["federal_reserve_press_rss"]
    assert report["coverage_audit"]["audit_status"] == "fail_source_coverage"
