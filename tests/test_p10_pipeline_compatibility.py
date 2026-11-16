import json
from datetime import date, datetime, timezone
from pathlib import Path

from tools.research.p10.synthetic_pipeline import (
    build_synthetic_snapshot,
    validate_snapshot,
    write_snapshot,
)


def test_synthetic_snapshot_is_valid_same_day(tmp_path):
    p = tmp_path / "snapshot.json"
    write_snapshot(p, build_synthetic_snapshot())
    now = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    ok, errors = validate_snapshot(p, now=now)
    assert ok, errors


def test_stale_snapshot_is_blocked(tmp_path):
    p = tmp_path / "snapshot.json"
    write_snapshot(p, build_synthetic_snapshot(date(2026, 10, 1)))
    now = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    ok, errors = validate_snapshot(p, now=now)
    assert not ok
    assert any("STALE_DATA" in e for e in errors)


def test_tamper_and_missing_ticker_are_blocked(tmp_path):
    p = tmp_path / "snapshot.json"
    d = build_synthetic_snapshot()
    d["ohlcv"] = [r for r in d["ohlcv"] if r["ticker"] != "AAPL"]
    p.write_text(json.dumps(d), encoding="utf-8")
    now = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    ok, errors = validate_snapshot(p, now=now)
    assert not ok
    assert "SHA256_MISMATCH" in errors
    assert any("MISSING_TICKER AAPL" in e for e in errors)


def test_membership_and_assetid_are_present():
    d = build_synthetic_snapshot()
    assert d["synthetic"] is True
    assert {r["ticker"] for r in d["ohlcv"]} == {"AAPL", "MSFT", "NVDA", "BRK.B", "WBA"}
    assert all("assetid" in r for r in d["ohlcv"])
    assert all("effective_date" in r for r in d["membership"])
    assert all(isinstance(r["is_member"], bool) for r in d["membership"])
