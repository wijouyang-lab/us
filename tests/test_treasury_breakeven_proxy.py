import pytest

from tools.research.treasury_breakeven_proxy import build_breakeven_proxy


def snapshot(curve_type, retrieved_at, rows, url):
    return {
        "metadata": {
            "curve_type": curve_type,
            "retrieved_at_utc": retrieved_at,
            "source_url": url,
        },
        "rows": rows,
    }


def test_breakeven_proxy_joins_dates_and_uses_later_retrieval_time():
    nominal = snapshot("nominal", "2026-10-23T16:00:00Z", [
        {"observation_date": "2026-10-20", "yield_pct": {"5y": 4.0, "10y": 4.5, "20y": 4.7}},
        {"observation_date": "2026-10-21", "yield_pct": {"5y": 4.1, "10y": 4.6, "20y": 4.8}},
        {"observation_date": "2026-10-22", "yield_pct": {"5y": 4.2, "10y": 4.7, "20y": 4.9}},
    ], "https://home.treasury.gov/nominal.xml")
    real = snapshot("real", "2026-10-24T12:00:00Z", [
        {"observation_date": "2026-10-20", "yield_pct": {"5y": 1.5, "10y": 2.0, "20y": 2.2}},
        {"observation_date": "2026-10-22", "yield_pct": {"5y": 1.7, "10y": 2.1, "20y": None}},
        {"observation_date": "2026-10-23", "yield_pct": {"5y": 1.8, "10y": 2.2, "20y": 2.4}},
    ], "https://home.treasury.gov/real.xml")
    result = build_breakeven_proxy(nominal, real)
    assert result["metadata"]["row_count"] == 2
    assert result["metadata"]["unmatched_nominal_dates"] == 1
    assert result["metadata"]["unmatched_real_dates"] == 1
    assert result["metadata"]["available_at_utc"] == "2026-10-24T12:00:00Z"
    assert result["rows"][0]["breakeven_proxy_bp"]["5y"] == 250.0
    assert result["rows"][0]["breakeven_proxy_bp"]["10y"] == 250.0
    assert result["rows"][1]["breakeven_proxy_bp"]["20y"] is None
    assert result["rows"][1]["availability_rule"] == "usable_only_at_or_after_available_at_utc"
    assert result["metadata"]["production_scanner_modified"] is False
    assert any("not a pure expected-inflation measure" in x for x in result["metadata"]["limitations"])


@pytest.mark.parametrize("bad_timestamp", ["", "2026-10-24T12:00:00"])
def test_breakeven_proxy_rejects_missing_or_naive_retrieval_timestamps(bad_timestamp):
    nominal = snapshot("nominal", bad_timestamp, [], "https://home.treasury.gov/nominal.xml")
    real = snapshot("real", "2026-10-24T12:00:00Z", [], "https://home.treasury.gov/real.xml")
    with pytest.raises(ValueError, match="timezone-aware"):
        build_breakeven_proxy(nominal, real)


def test_breakeven_proxy_rejects_wrong_curve_type_and_duplicate_dates():
    nominal = snapshot("real", "2026-10-23T16:00:00Z", [], "https://home.treasury.gov/nominal.xml")
    real = snapshot("real", "2026-10-24T12:00:00Z", [], "https://home.treasury.gov/real.xml")
    with pytest.raises(ValueError, match="curve_type=nominal"):
        build_breakeven_proxy(nominal, real)
    nominal = snapshot("nominal", "2026-10-23T16:00:00Z", [
        {"observation_date": "2026-10-20", "yield_pct": {}},
        {"observation_date": "2026-10-20", "yield_pct": {}},
    ], "https://home.treasury.gov/nominal.xml")
    with pytest.raises(ValueError, match="duplicate observation_date"):
        build_breakeven_proxy(nominal, real)


def test_breakeven_proxy_rejects_observation_after_retrieval_date():
    nominal = snapshot("nominal", "2026-10-20T16:00:00Z", [
        {"observation_date": "2026-10-21", "yield_pct": {"10y": 4.0}},
    ], "https://home.treasury.gov/nominal.xml")
    real = snapshot("real", "2026-10-20T16:00:00Z", [], "https://home.treasury.gov/real.xml")
    with pytest.raises(ValueError, match="after retrieval date"):
        build_breakeven_proxy(nominal, real)
