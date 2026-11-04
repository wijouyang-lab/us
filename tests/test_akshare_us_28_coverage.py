import pandas as pd

from tools.research.akshare_us_28_coverage import (
    SAMPLE_TICKERS,
    assess_history,
    build_spot_index,
    normalize_ticker,
)


def test_sample_is_the_audited_fixed_28():
    assert len(SAMPLE_TICKERS) == 28
    assert len(set(SAMPLE_TICKERS)) == 28
    assert "BRK.B" in SAMPLE_TICKERS


def test_normalize_vendor_ticker_class_shares():
    assert normalize_ticker("BRK.B") == "BRKB"
    assert normalize_ticker("BRK-B") == "BRKB"
    assert normalize_ticker("105.BRK-B") == "105BRKB"


def test_build_spot_index_uses_vendor_code_suffix():
    spot = pd.DataFrame(
        [
            {"代码": "105.AAPL", "最新价": 200.0, "总市值": 1.0e12, "市盈率": 30.0, "名称": "Apple"},
            {"代码": "106.BRK-B", "最新价": 500.0, "总市值": 1.0e11, "市盈率": 10.0, "名称": "Berkshire"},
        ]
    )
    indexed = build_spot_index(spot)
    assert indexed["AAPL"][0]["vendor_symbol"] == "105.AAPL"
    assert indexed["BRKB"][0]["vendor_symbol"] == "106.BRK-B"
    assert indexed["AAPL"][0]["quote_price"] == 200.0


def test_build_spot_index_preserves_duplicate_matches_as_ambiguous():
    spot = pd.DataFrame(
        [
            {"代码": "105.AAPL", "最新价": 200.0, "总市值": 1.0, "市盈率": 30.0},
            {"代码": "106.AAPL", "最新价": 201.0, "总市值": 1.0, "市盈率": 30.0},
        ]
    )
    assert len(build_spot_index(spot)["AAPL"]) == 2


def test_assess_history_passes_clean_data():
    frame = pd.DataFrame(
        [
            {"日期": "2026-01-02", "开盘": 10.0, "收盘": 11.0, "最高": 12.0, "最低": 9.0, "成交量": 100},
            {"日期": "2026-01-05", "开盘": 11.0, "收盘": 10.5, "最高": 11.5, "最低": 10.0, "成交量": 120},
        ]
    )
    result = assess_history(frame)
    assert result["quality_pass"] is True
    assert result["rows"] == 2
    assert result["date_min"] == "2026-01-02"
    assert result["date_max"] == "2026-01-05"


def test_assess_history_fails_duplicate_and_bad_ohlc():
    frame = pd.DataFrame(
        [
            {"日期": "2026-01-02", "开盘": 10.0, "收盘": 11.0, "最高": 12.0, "最低": 9.0, "成交量": 100},
            {"日期": "2026-01-02", "开盘": 10.0, "收盘": 15.0, "最高": 12.0, "最低": 9.0, "成交量": 0},
        ]
    )
    result = assess_history(frame)
    assert result["quality_pass"] is False
    assert result["duplicates"] == 2
    assert result["invalid_ohlc"] == 1


def test_assess_history_reports_empty_and_schema_mismatch():
    assert assess_history(pd.DataFrame())["quality_status"] == "NO_HISTORY"
    result = assess_history(pd.DataFrame([{"日期": "2026-01-02"}]))
    assert result["quality_status"] == "SCHEMA_MISMATCH"
