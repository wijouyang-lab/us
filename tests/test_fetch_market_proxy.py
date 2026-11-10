# -*- coding: utf-8 -*-
"""Tests for SPY proxy normalization; no network."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import fetch_market_proxy as mod  # noqa: E402


def test_proxy_normalizes_adjusted_and_deduplicates():
    raw = pd.DataFrame(
        [
            {"Open": 100, "High": 102, "Low": 99, "Close": 101, "Adj Close": 100.5, "Volume": 1000},
            {"Open": 101, "High": 103, "Low": 100, "Close": 102, "Adj Close": 101.5, "Volume": 1100},
        ],
        index=pd.to_datetime(["2026-10-26", "2026-10-27"]),
    )
    df, report = mod.normalize(raw, "test", "2026-10-28T00:00:00Z")
    assert len(df) == 2
    assert report["adjusted_close_available"] is True
    assert df["Ticker"].unique().tolist() == ["SPY"]


def test_proxy_drops_invalid_ohlc():
    raw = pd.DataFrame(
        [{"Open": 100, "High": 1, "Low": 99, "Close": 101, "Adj Close": 100.5, "Volume": 1000}],
        index=pd.to_datetime(["2026-10-27"]),
    )
    df, report = mod.normalize(raw, "test", "2026-10-28T00:00:00Z")
    assert len(df) == 0
    assert report["adjusted_close_available"] is False
