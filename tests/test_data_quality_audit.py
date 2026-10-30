# -*- coding: utf-8 -*-
"""Tests for Phase 2.1 price-panel audit."""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from data_quality_audit import summarize_price_panel  # noqa: E402


def test_summarize_detects_bad_ohlc_and_duplicate():
    df = pd.DataFrame([
        {"Date": "2024-01-02", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 100},
        {"Date": "2024-01-02", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 100},
        {"Date": "2024-01-03", "Ticker": "AAA", "Open": 10, "High": 9, "Low": 11, "Close": 10, "Volume": 0},
    ])
    out = summarize_price_panel(df)
    assert out["duplicate_ticker_date"] == 1
    assert out["ohlc_invalid"] == 1
    assert out["zero_volume"] == 1


def test_summarize_preserves_date_range_and_ticker_count():
    df = pd.DataFrame([
        {"Date": "2024-01-02", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 100},
        {"Date": "2024-01-03", "Ticker": "BBB", "Open": 20, "High": 21, "Low": 19, "Close": 20, "Volume": 100},
    ])
    out = summarize_price_panel(df)
    assert out["tickers"] == 2
    assert out["date_min"] == "2024-01-02"
    assert out["date_max"] == "2024-01-03"
    assert out["ohlc_invalid"] == 0
