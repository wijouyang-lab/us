import json
from datetime import timedelta
from pathlib import Path

import pytest

import tools.research.run_event_capture_cycle as cycle
from tools.research.pit_event_records import normalize_event


def sample_event():
    event = normalize_event(
        source="bls_cpi_rss",
        source_event_id="cpi-item-1",
        event_type="macro_release",
        published_at_utc="2026-10-23T12:00:00Z",
        first_seen_at_utc="2026-10-23T12:01:00Z",
        raw_payload={"headline": "CPI report"},
    )
    event.update({
        "actual_value": 3.1,
        "consensus_value": 3.0,
        "consensus_asof_utc": "2026-10-23T11:30:00Z",
    })
    return event


class FakeRssCollector:
    def __init__(self, user_agent, **kwargs):
        assert "@" in user_agent

    def collect(self, feed_keys):
        assert feed_keys == ["bls_cpi"]
        return {
            "events": [sample_event()],
            "metadata": {
                "requested_feed_keys": feed_keys,
                "event_count": 1,
                "feed_reports": [{"feed_key": "bls_cpi", "status": "ok", "event_count": 1}],
            },
        }


def test_one_command_capture_archive_and_audit_pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "OfficialRssCollector", FakeRssCollector)
    result = cycle.run_cycle(
        output_dir=tmp_path,
        decision_at="2026-10-23T13:00:00Z",
        feed_keys=["bls_cpi"],
        feed_user_agent="Quant research tester@quantlab.dev",
        max_age_by_type={"macro_release": timedelta(days=1)},
    )
    assert result["event_count"] == 1
    assert result["successful_source_count"] == 1
    assert not result["all_sources_failed"]
    for key in ("events_path", "metadata_path", "archive_path", "audit_path"):
        assert Path(result[key]).exists()
    audit = json.loads(Path(result["audit_path"]).read_text(encoding="utf-8"))
    assert audit["coverage_audit"]["eligible_events"] == 1
    assert audit["macro_surprise"]["eligible_count"] == 1
    assert audit["research_only"] is True
    assert audit["trading_signal_generated"] is False
    source_coverage = audit["capture_cycle"]["source_collection_coverage"]
    assert source_coverage == [{
        "source_kind": "official_rss",
        "feed_key": "bls_cpi",
        "source": "bls_cpi_rss",
        "status": "ok",
        "event_count": 1,
        "item_count": None,
        "error_type": None,
    }]


def test_successful_empty_feed_is_visible_in_source_coverage(tmp_path, monkeypatch):
    class EmptySuccessCollector:
        def __init__(self, user_agent, **kwargs):
            assert "@" in user_agent

        def collect(self, feed_keys):
            return {
                "events": [],
                "metadata": {
                    "requested_feed_keys": feed_keys,
                    "event_count": 0,
                    "feed_reports": [{
                        "feed_key": "bls_cpi",
                        "status": "ok",
                        "event_count": 0,
                        "item_count": 0,
                    }],
                },
            }

    monkeypatch.setattr(cycle, "OfficialRssCollector", EmptySuccessCollector)
    result = cycle.run_cycle(
        output_dir=tmp_path,
        decision_at="2026-10-23T13:00:00Z",
        feed_keys=["bls_cpi"],
        feed_user_agent="Quant research tester@quantlab.dev",
    )
    audit = json.loads(Path(result["audit_path"]).read_text(encoding="utf-8"))
    assert result["successful_source_count"] == 1
    assert audit["capture_cycle"]["source_collection_coverage"][0]["status"] == "ok"
    assert audit["capture_cycle"]["source_collection_coverage"][0]["event_count"] == 0
    assert audit["coverage_audit"]["audit_status"] == "fail_no_data"


def test_repeated_capture_deduplicates_the_same_event_version(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "OfficialRssCollector", FakeRssCollector)
    args = dict(
        output_dir=tmp_path,
        decision_at="2026-10-23T13:00:00Z",
        feed_keys=["bls_cpi"],
        feed_user_agent="Quant research tester@quantlab.dev",
    )
    first = cycle.run_cycle(**args)
    second = cycle.run_cycle(**args)
    assert first["events_path"] != second["events_path"]
    assert first["archive_path"] == second["archive_path"]
    update = second["report"]["capture_cycle"]["archive_update"]
    assert update["new_version_count"] == 0
    assert update["duplicate_version_count"] == 1
    assert len(json.loads(Path(second["archive_path"]).read_text(encoding="utf-8"))) == 1


def test_invalid_decision_time_fails_before_source_initialization(tmp_path, monkeypatch):
    class MustNotRun:
        def __init__(self, *args, **kwargs):
            pytest.fail("source collector must not initialize for invalid decision time")
    monkeypatch.setattr(cycle, "OfficialRssCollector", MustNotRun)
    with pytest.raises(ValueError, match="timezone-aware"):
        cycle.run_cycle(
            output_dir=tmp_path,
            decision_at="2026-10-23T13:00:00",
            feed_keys=["bls_cpi"],
        )


def test_all_feed_failures_are_recorded_and_signaled(tmp_path, monkeypatch):
    class FailedCollector:
        def __init__(self, user_agent, **kwargs):
            assert "@" in user_agent
        def collect(self, feed_keys):
            return {
                "events": [],
                "metadata": {
                    "requested_feed_keys": feed_keys,
                    "event_count": 0,
                    "feed_reports": [{
                        "feed_key": feed_keys[0],
                        "status": "fetch_or_parse_error",
                        "event_count": 0,
                    }],
                },
            }
    monkeypatch.setattr(cycle, "OfficialRssCollector", FailedCollector)
    result = cycle.run_cycle(
        output_dir=tmp_path,
        decision_at="2026-10-23T13:00:00Z",
        feed_keys=["bls_cpi"],
        feed_user_agent="Quant research tester@quantlab.dev",
    )
    assert result["all_sources_failed"]
    metadata = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["source_reports"]["official_rss"]["feed_reports"][0]["status"] == "fetch_or_parse_error"


def test_max_age_config_validates_values():
    assert cycle._parse_max_age_days('{"macro_release":2}') == {"macro_release": timedelta(days=2)}
    with pytest.raises(ValueError, match="finite non-negative"):
        cycle._parse_max_age_days('{"macro_release":-1}')
    with pytest.raises(ValueError, match="finite non-negative"):
        cycle._parse_max_age_days('{"macro_release":1e999}')
