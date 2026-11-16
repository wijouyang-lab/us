import json
from datetime import date, datetime, timezone
from pathlib import Path

from tools.research.p10.synthetic_pipeline import (
    build_synthetic_snapshot,
    commit_bundle,
    expected_last_us_session,
    make_manifest,
    validate_bundle,
    write_bundle,
)

KEY = "synthetic-test-key-not-a-real-secret"
NOW = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)


def _bundle(tmp_path, data=None, version=1):
    data = data or build_synthetic_snapshot(NOW)
    d, m = write_bundle(tmp_path, data, KEY, version)
    return data, d, m


def _rewrite(tmp_path, data):
    d = tmp_path / "snapshot.json"
    m = tmp_path / "manifest.json"
    d.write_text(json.dumps(data), encoding="utf-8")
    m.write_text(json.dumps(make_manifest(data, KEY)), encoding="utf-8")
    return d, m


def test_valid_synthetic_bundle():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        _, d, m = _bundle(Path(td))
        result = validate_bundle(d, m, KEY, now=NOW)
        assert result["ok"], result["errors"]
        assert result["metrics"]["ticker_coverage"] == 1.0
        assert result["metrics"]["member_day_coverage"] == 1.0


def test_actual_ohlcv_latest_lag_blocks_despite_metadata(tmp_path):
    data, _, _ = _bundle(tmp_path)
    data["ohlcv"] = [r for r in data["ohlcv"] if not (r["ticker"] == "AAPL" and r["date"] == "2026-11-13")]
    data["reported_latest_price_date"] = "2026-11-13"
    d, m = _rewrite(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert any("PER_TICKER_LATEST_LAG AAPL" in e for e in result["errors"])


def test_overall_metadata_claim_cannot_override_actual_rows(tmp_path):
    data, _, _ = _bundle(tmp_path)
    data["ohlcv"] = [r for r in data["ohlcv"] if r["date"] != "2026-11-13"]
    data["reported_latest_price_date"] = "2026-11-13"
    d, m = _rewrite(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert "REPORTED_LATEST_MISMATCH" in result["errors"]


def test_membership_metadata_claim_blocks_when_rows_lag(tmp_path):
    data, _, _ = _bundle(tmp_path)
    data["membership"] = [r for r in data["membership"] if r["date"] != "2026-11-13"]
    data["reported_membership_latest_date"] = "2026-11-13"
    d, m = _rewrite(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert "MEMBERSHIP_LATEST_LAG" in result["errors"]
    assert "REPORTED_MEMBERSHIP_MISMATCH" in result["errors"]


def test_false_membership_is_valid_not_missing(tmp_path):
    data, _, _ = _bundle(tmp_path)
    for r in data["membership"]:
        if r["ticker"] == "WBA" and r["date"] == "2026-11-13":
            r["is_member"] = False
    d, m = _rewrite(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert result["ok"], result["errors"]
    assert result["metrics"]["member_day_coverage"] > 0.99


def test_missing_membership_record_blocks(tmp_path):
    data, _, _ = _bundle(tmp_path)
    data["membership"] = [r for r in data["membership"] if not (r["ticker"] == "AAPL" and r["date"] == "2026-11-13")]
    d, m = _rewrite(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert any("MEMBERSHIP_RECORD_MISSING" in e for e in result["errors"])
    assert any("MEMBERSHIP_DAY_INCOMPLETE" in e for e in result["errors"])


def test_missing_independent_baseline_is_not_verifiable(tmp_path):
    data, _, _ = _bundle(tmp_path)
    data["expected_membership"] = []
    d, m = _rewrite(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert "EXPECTED_MEMBERSHIP_NOT_VERIFIABLE" in result["errors"]
    assert result["metrics"]["member_day_coverage"] is None


def test_non_core_missing_allowed_at_98_percent(tmp_path):
    data, _, _ = _bundle(tmp_path)
    data["ohlcv"] = [r for r in data["ohlcv"] if r["ticker"] != "T000"]
    d, m = _rewrite(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert result["ok"], result["errors"]
    assert result["metrics"]["ticker_coverage"] == 0.98


def test_core_ticker_missing_blocks_even_at_98_percent(tmp_path):
    data, _, _ = _bundle(tmp_path)
    data["ohlcv"] = [r for r in data["ohlcv"] if r["ticker"] != "AAPL"]
    d, m = _rewrite(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert any("CORE_TICKER_MISSING AAPL" in e for e in result["errors"])


def test_commit_updates_state_and_blocks_rollback_and_duplicate(tmp_path):
    state = tmp_path / "state.json"
    data = build_synthetic_snapshot(NOW)
    d1, m1 = write_bundle(tmp_path / "v1", data, KEY, 1)
    r1 = commit_bundle(d1, m1, KEY, state_path=state, now=NOW)
    assert r1["ok"] and r1["committed"]
    assert json.loads(state.read_text())["last_version"] == 1
    d2, m2 = write_bundle(tmp_path / "v2", data, KEY, 2)
    r2 = commit_bundle(d2, m2, KEY, state_path=state, now=NOW)
    assert r2["committed"]
    assert json.loads(state.read_text())["last_version"] == 2
    d0, m0 = write_bundle(tmp_path / "v0", data, KEY, 1)
    assert not commit_bundle(d0, m0, KEY, state_path=state, now=NOW)["committed"]
    assert "ROLLBACK" in " ".join(commit_bundle(d0, m0, KEY, state_path=state, now=NOW)["errors"])
    d2b, m2b = write_bundle(tmp_path / "v2b", data, KEY, 2)
    assert "DUPLICATE_VERSION" in " ".join(commit_bundle(d2b, m2b, KEY, state_path=state, now=NOW)["errors"])


def test_state_write_failure_does_not_commit(tmp_path):
    _, d, m = _bundle(tmp_path)
    missing_parent = tmp_path / "missing" / "state.json"
    result = commit_bundle(d, m, KEY, state_path=missing_parent, now=NOW)
    assert not result["committed"]
    assert "STATE_WRITE_FAILED" in result["errors"]
    assert not missing_parent.exists()


def test_p9_full_history_boundaries(tmp_path):
    data = build_synthetic_snapshot(datetime(2025, 1, 1, 12, tzinfo=timezone.utc), scope="P9_FULL_HISTORY", ticker_count=5)
    d, m = write_bundle(tmp_path, data, KEY)
    result = validate_bundle(d, m, KEY, now=datetime(2025, 1, 1, 12, tzinfo=timezone.utc), expected_scope="P9_FULL_HISTORY")
    assert result["ok"], result["errors"]
    data["ohlcv"] = [r for r in data["ohlcv"] if r["date"] != "2007-05-30"]
    d, m = _rewrite(tmp_path, data)
    assert any("P9_START_MISMATCH" in e for e in validate_bundle(d, m, KEY, now=datetime(2025, 1, 1, 12, tzinfo=timezone.utc))["errors"])


def test_trial_cannot_claim_full_history(tmp_path):
    data = build_synthetic_snapshot(NOW)
    _, d, m = _bundle(tmp_path, data)
    result = validate_bundle(d, m, KEY, now=NOW, expected_scope="P9_FULL_HISTORY")
    assert "SCOPE_MISMATCH" in result["errors"]


def test_bad_ohlcv_and_timestamp_are_blocked(tmp_path):
    data, _, _ = _bundle(tmp_path)
    data["ohlcv"][0]["high"] = -1
    d, m = _rewrite(tmp_path, data)
    assert any("NON_POSITIVE_OHLCV" in e or "BAD_OHLCV_RANGE" in e for e in validate_bundle(d, m, KEY, now=NOW)["errors"])
    data2, _, _ = _bundle(tmp_path / "t")
    data2["data_updated_at"] = "2026-11-13T22:00:00"
    d2, m2 = _rewrite(tmp_path / "t", data2)
    assert "TIMESTAMP_WITHOUT_TIMEZONE" in validate_bundle(d2, m2, KEY, now=NOW)["errors"]


def test_us_calendar_holiday_and_early_close():
    assert expected_last_us_session(datetime(2026, 11, 26, 23, tzinfo=timezone.utc)).isoformat() == "2026-11-25"
    assert expected_last_us_session(datetime(2026, 11, 27, 18, tzinfo=timezone.utc)).isoformat() == "2026-11-27"
    assert expected_last_us_session(datetime(2026, 11, 27, 16, tzinfo=timezone.utc)).isoformat() == "2026-11-25"
    assert expected_last_us_session(datetime(2026, 11, 28, 23, tzinfo=timezone.utc)).isoformat() == "2026-11-27"
