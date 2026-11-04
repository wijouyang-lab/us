import pandas as pd
from tools.research.akshare_us_28_coverage import (
    SAMPLE_TICKERS, assess_history, build_spot_index, normalize_ticker,
    COL_CODE, COL_NAME, COL_PRICE, COL_MARKET_CAP, COL_PE,
    COL_DATE, COL_OPEN, COL_CLOSE, COL_HIGH, COL_LOW, COL_VOLUME,
)


def row(code, price=200.0, cap=1.0e12, pe=30.0, name="Company"):
    return {COL_CODE: code, COL_NAME: name, COL_PRICE: price,
            COL_MARKET_CAP: cap, COL_PE: pe}


def hist(rows):
    return pd.DataFrame(rows)


def test_sample_is_the_audited_fixed_28():
    assert len(SAMPLE_TICKERS) == 28
    assert len(set(SAMPLE_TICKERS)) == 28
    assert "BRK.B" in SAMPLE_TICKERS


def test_normalize_vendor_ticker_class_shares():
    assert normalize_ticker("BRK.B") == "BRKB"
    assert normalize_ticker("BRK-B") == "BRKB"
    assert normalize_ticker("105.BRK-B") == "105BRKB"


def test_build_spot_index_uses_vendor_code_suffix():
    spot = pd.DataFrame([row("105.AAPL"), row("106.BRK-B", price=500.0, cap=1.0e11, name="Berkshire")])
    indexed = build_spot_index(spot)
    assert indexed["AAPL"][0]["vendor_symbol"] == "105.AAPL"
    assert indexed["BRKB"][0]["vendor_symbol"] == "106.BRK-B"
    assert indexed["AAPL"][0]["quote_price"] == 200.0


def test_build_spot_index_preserves_duplicate_matches_as_ambiguous():
    spot = pd.DataFrame([row("105.AAPL"), row("106.AAPL", price=201.0)])
    assert len(build_spot_index(spot)["AAPL"]) == 2


def test_assess_history_passes_clean_data():
    frame = hist([
        {COL_DATE: "2026-01-02", COL_OPEN: 10.0, COL_CLOSE: 11.0, COL_HIGH: 12.0, COL_LOW: 9.0, COL_VOLUME: 100},
        {COL_DATE: "2026-01-05", COL_OPEN: 11.0, COL_CLOSE: 10.5, COL_HIGH: 11.5, COL_LOW: 10.0, COL_VOLUME: 120},
    ])
    result = assess_history(frame)
    assert result["quality_pass"] is True
    assert result["rows"] == 2
    assert result["date_min"] == "2026-01-02"
    assert result["date_max"] == "2026-01-05"


def test_assess_history_fails_duplicate_and_bad_ohlc():
    frame = hist([
        {COL_DATE: "2026-01-02", COL_OPEN: 10.0, COL_CLOSE: 11.0, COL_HIGH: 12.0, COL_LOW: 9.0, COL_VOLUME: 100},
        {COL_DATE: "2026-01-02", COL_OPEN: 10.0, COL_CLOSE: 15.0, COL_HIGH: 12.0, COL_LOW: 9.0, COL_VOLUME: 0},
    ])
    result = assess_history(frame)
    assert result["quality_pass"] is False
    assert result["duplicates"] == 2
    assert result["invalid_ohlc"] == 1


def test_assess_history_reports_empty_and_schema_mismatch():
    assert assess_history(pd.DataFrame())["quality_status"] == "NO_HISTORY"
    result = assess_history(pd.DataFrame([{COL_DATE: "2026-01-02"}]))
    assert result["quality_status"] == "SCHEMA_MISMATCH"
