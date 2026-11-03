# -*- coding: utf-8 -*-
"""Additional behavior tests for macro verification and Data Health."""
import json
from pathlib import Path

from dashboard_export import _read_macro_forecast, _valid_release_date

ROOT = Path(__file__).resolve().parents[1]


def _forecast(tmp_path, **over):
    row = {
        "key": "cpi_yoy", "indicator": "CPI", "period": "2026年9月",
        "forecast": 3.6, "actual": 3.7, "previous": None,
        "unit": "%", "released_at": "2026-10-15", "source": "BLS",
        "source_status": "verified", "fetched_at": "2026-10-15T12:00:00Z",
        "actual_period": "2026-09", "forecast_period": "2026-09",
        "actual_indicator": "CPI", "forecast_indicator": "CPI",
    }
    row.update(over)
    d = tmp_path / "dashboard" / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "macro_forecast.json").write_text(json.dumps({"items": [row]}), encoding="utf-8")
    return _read_macro_forecast(tmp_path)


def test_verified_period_can_differ_from_release_month(tmp_path):
    out = _forecast(tmp_path)  # period Sep, released Oct
    item = out["items"][0]
    assert item["verification_status"] == "verified"
    assert item["surprise"] == 0.1


def test_missing_release_hides_surprise(tmp_path):
    item = _forecast(tmp_path, released_at=None)["items"][0]
    assert item["surprise"] is None
    assert item["verification_status"] == "unverified"


def test_missing_or_unparseable_period_hides_surprise(tmp_path):
    for period in (None, "最新"):
        item = _forecast(tmp_path, period=period, actual_period=None, forecast_period=None)["items"][0]
        assert item["surprise"] is None
        assert "period" in item["verification_reason"]


def test_period_mismatch_hides_surprise(tmp_path):
    item = _forecast(tmp_path, forecast_period="2026-08")["items"][0]
    assert item["surprise"] is None
    assert "mismatch" in item["verification_reason"]


def test_indicator_definition_mismatch_hides_surprise(tmp_path):
    item = _forecast(tmp_path, actual_indicator="CPI", forecast_indicator="Core CPI")["items"][0]
    assert item["surprise"] is None
    assert "indicator" in item["verification_reason"]


def test_fallback_source_hides_surprise(tmp_path):
    item = _forecast(tmp_path, source_status="fallback")["items"][0]
    assert item["surprise"] is None


def test_release_date_accepts_only_complete_iso_date_or_datetime():
    assert _valid_release_date("2026-10-15")
    assert _valid_release_date("2026-10-15T13:30:00Z")
    assert _valid_release_date("2026-10-15T13:30:00.1Z")
    assert _valid_release_date("2026-10-15T13:30:00.123456+08:00")
    assert not _valid_release_date("2026-10-15T13:30:00.1234567Z")
    assert not _valid_release_date("2026-10-15T13:30:00")
    assert not _valid_release_date("2026-10-15T13:30:00+24:00")
    assert not _valid_release_date("2026-02-31")
    assert not _valid_release_date("2026-10-15garbage")
    assert not _valid_release_date("2026-10-15T99:99:99")
    assert not _valid_release_date("")
    assert not _valid_release_date(None)


def test_invalid_release_date_stays_unverified_without_surprise(tmp_path):
    for bad in ("2026-10-15garbage", "2026-02-31", "2026-10-15T99:99:99",
                "2026-10-15T13:30:00.1234567Z", "2026-10-15T13:30:00",
                "2026-10-15T13:30:00+24:00"):
        item = _forecast(tmp_path / bad.replace(":", "_").replace("+", "_"), released_at=bad)["items"][0]
        assert item["verification_status"] == "unverified"
        assert item["surprise"] is None
        assert "影响文案已隐藏" in item["impact"]
