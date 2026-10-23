import json

import pytest

from tools.research.run_pit_event_audit import load_event_rows, main, parse_max_age_days


def test_load_event_rows_requires_json_array_of_objects(tmp_path):
    path = tmp_path / "events.json"
    path.write_text('[{"event_type":"other"}]', encoding="utf-8")
    assert load_event_rows(path) == [{"event_type": "other"}]

    path.write_text('{"event_type":"other"}', encoding="utf-8")
    with pytest.raises(ValueError, match="must be an array"):
        load_event_rows(path)

    path.write_text('[{"ok":true}, null]', encoding="utf-8")
    with pytest.raises(ValueError, match="every input"):
        load_event_rows(path)


def test_parse_max_age_days_validates_values():
    ages = parse_max_age_days('{"macro_release": 1.5, "earnings": 3}')
    assert ages["macro_release"].total_seconds() == 1.5 * 86400
    assert ages["earnings"].total_seconds() == 3 * 86400

    with pytest.raises(ValueError, match="non-negative"):
        parse_max_age_days('{"macro_release": -1}')
    with pytest.raises(ValueError, match="must be a number"):
        parse_max_age_days('{"macro_release": "two"}')


def test_cli_writes_reproducible_report_to_requested_path(tmp_path):
    source = tmp_path / "events.json"
    output = tmp_path / "report.json"
    source.write_text(json.dumps([{
        "event_id": "event-1",
        "event_type": "other",
        "availability_status": "available",
        "published_at_utc": "2026-10-15T10:00:00Z",
        "first_seen_at_utc": "2026-10-15T10:01:00Z",
    }]), encoding="utf-8")

    result = main([
        "--input", str(source),
        "--decision-at", "2026-10-15T12:00:00Z",
        "--output", str(output),
    ])
    report = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert report["input_event_count"] == 1
    assert len(report["input_snapshot_sha256"]) == 64
    assert report["trading_signal_generated"] is False


def test_cli_rejects_non_timezone_aware_decision(tmp_path, capsys):
    source = tmp_path / "events.json"
    source.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["--input", str(source), "--decision-at", "2026-10-15T12:00:00"])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "timezone-aware" in captured.err



def test_cli_expected_sources_are_reported_as_coverage_failure(tmp_path):
    source = tmp_path / "events.json"
    output = tmp_path / "report.json"
    source.write_text(json.dumps([{
        "event_id": "event-1",
        "source": "bls_cpi_rss",
        "event_type": "macro_release",
        "availability_status": "available",
        "published_at_utc": "2026-10-15T10:00:00Z",
        "first_seen_at_utc": "2026-10-15T10:01:00Z",
    }]), encoding="utf-8")

    result = main([
        "--input", str(source),
        "--decision-at", "2026-10-15T12:00:00Z",
        "--expected-sources", "bls_cpi_rss,federal_reserve_press_rss",
        "--output", str(output),
    ])
    report = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert report["coverage_audit"]["missing_sources"] == ["federal_reserve_press_rss"]
    assert report["coverage_audit"]["audit_status"] == "fail_source_coverage"


def test_cli_empty_input_is_written_as_fail_no_data(tmp_path):
    source = tmp_path / "events.json"
    output = tmp_path / "report.json"
    source.write_text("[]", encoding="utf-8")

    result = main([
        "--input", str(source),
        "--decision-at", "2026-10-15T12:00:00Z",
        "--output", str(output),
    ])
    report = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert report["coverage_audit"]["audit_status"] == "fail_no_data"
    assert report["coverage_audit"]["eligible_rate"] == 0.0
