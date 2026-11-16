import json
from datetime import datetime, timezone
from pathlib import Path

from tools.research.p10.synthetic_pipeline import (
    build_synthetic_snapshot,
    expected_last_us_session,
    make_manifest,
    sha256,
    validate_bundle,
    write_bundle,
)

KEY = "synthetic-test-key-not-a-real-secret"
NOW = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)


def _bundle(tmp_path, key=KEY, version=1, now=NOW):
    data = build_synthetic_snapshot(now)
    d, m = write_bundle(tmp_path, data, key, version)
    return data, d, m


def test_valid_synthetic_bundle_and_metrics(tmp_path):
    _, d, m = _bundle(tmp_path)
    result = validate_bundle(d, m, KEY, now=NOW)
    assert result["ok"], result["errors"]
    assert result["synthetic"] is True
    assert result["metrics"]["ticker_coverage"] == 1.0
    assert result["metrics"]["member_day_coverage"] == 1.0


def test_stale_price_date_blocks_even_if_update_time_is_fresh(tmp_path):
    data, d, m = _bundle(tmp_path)
    data["latest_price_date"] = "2026-11-12"
    d.write_text(json.dumps(data), encoding="utf-8")
    m.write_text(json.dumps(make_manifest(data, KEY)), encoding="utf-8")
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert any("LATEST_PRICE_DATE_LAG" in e for e in result["errors"])


def test_single_ticker_latest_date_missing_blocks(tmp_path):
    data, d, m = _bundle(tmp_path)
    data["per_ticker_latest_price_date"]["AAPL"] = "2026-11-12"
    d.write_text(json.dumps(data), encoding="utf-8")
    m.write_text(json.dumps(make_manifest(data, KEY)), encoding="utf-8")
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert any("PER_TICKER_LATEST_MISSING AAPL" in e for e in result["errors"])


def test_missing_membership_day_blocks(tmp_path):
    data, d, m = _bundle(tmp_path)
    data["membership"] = [r for r in data["membership"] if r["date"] != "2026-11-12"]
    d.write_text(json.dumps(data), encoding="utf-8")
    m.write_text(json.dumps(make_manifest(data, KEY)), encoding="utf-8")
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert any("MEMBER_DAY_COVERAGE_LOW" in e for e in result["errors"])
    assert any("MEMBERSHIP_DAY_INCOMPLETE" in e for e in result["errors"])


def test_low_ticker_and_member_day_coverage_blocks(tmp_path):
    data, d, m = _bundle(tmp_path)
    data["ohlcv"] = [r for r in data["ohlcv"] if r["ticker"] != "MSFT"]
    data["membership"] = [r for r in data["membership"] if r["ticker"] != "MSFT"]
    d.write_text(json.dumps(data), encoding="utf-8")
    m.write_text(json.dumps(make_manifest(data, KEY)), encoding="utf-8")
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert any("TICKER_COVERAGE_LOW" in e for e in result["errors"])
    assert any("MEMBER_DAY_COVERAGE_LOW" in e for e in result["errors"])


def test_data_and_sha_changed_but_hmac_not_updated_blocks(tmp_path):
    data, d, m = _bundle(tmp_path)
    data["ohlcv"][0]["close"] += 1.0
    manifest = json.loads(m.read_text())
    manifest["data_sha256"] = sha256(data)
    d.write_text(json.dumps(data), encoding="utf-8")
    m.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate_bundle(d, m, KEY, now=NOW)
    assert not result["ok"]
    assert "HMAC_MISMATCH" in result["errors"]


def test_missing_signature_and_wrong_key_block(tmp_path):
    data, d, m = _bundle(tmp_path)
    manifest = json.loads(m.read_text())
    manifest.pop("hmac_sha256")
    m.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate_bundle(d, m, KEY, now=NOW)
    assert "MISSING_SIGNATURE" in result["errors"]
    _, d2, m2 = _bundle(tmp_path / "other", key="wrong-key")
    result2 = validate_bundle(d2, m2, KEY, now=NOW)
    assert "HMAC_MISMATCH" in result2["errors"]


def test_rollback_and_duplicate_version_block(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"last_version": 2}))
    data = build_synthetic_snapshot(NOW)
    d1, m1 = write_bundle(tmp_path / "v1", data, KEY, version=1)
    assert "ROLLBACK" in " ".join(validate_bundle(d1, m1, KEY, now=NOW, state_path=state)["errors"])
    d2, m2 = write_bundle(tmp_path / "v2", data, KEY, version=2)
    assert "DUPLICATE_VERSION" in " ".join(validate_bundle(d2, m2, KEY, now=NOW, state_path=state)["errors"])


def test_schema_source_and_scope_mismatch_block(tmp_path):
    data, d, m = _bundle(tmp_path)
    data["schema"] = "wrong"
    data["source"] = "other"
    data["scope"] = "P9_FULL_HISTORY"
    d.write_text(json.dumps(data), encoding="utf-8")
    m.write_text(json.dumps(make_manifest(data, KEY)), encoding="utf-8")
    result = validate_bundle(d, m, KEY, now=NOW)
    assert "SCHEMA_MISMATCH" in result["errors"]
    assert "SOURCE_MISMATCH" in result["errors"]
    assert "SCOPE_MISMATCH" in result["errors"]


def test_us_holiday_and_early_close_calendar():
    assert expected_last_us_session(datetime(2026, 11, 26, 23, 0, tzinfo=timezone.utc)).isoformat() == "2026-11-25"
    assert expected_last_us_session(datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)).isoformat() == "2026-11-27"
    assert expected_last_us_session(datetime(2026, 11, 27, 16, 0, tzinfo=timezone.utc)).isoformat() == "2026-11-25"
    assert expected_last_us_session(datetime(2026, 11, 28, 23, 0, tzinfo=timezone.utc)).isoformat() == "2026-11-27"
