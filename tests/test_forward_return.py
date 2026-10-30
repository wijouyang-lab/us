# -*- coding: utf-8 -*-
"""Tests for forward-return labels."""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from forward_return import build_forward_returns  # noqa: E402


def prices():
    dates = pd.bdate_range("2024-01-02", periods=8)
    return pd.DataFrame({"Date": dates, "Ticker": "AAA", "Open": [10, 11, 12, 13, 14, 15, 16, 17]})


def test_matured_uses_next_open_and_trading_sessions():
    snap = pd.DataFrame([{"Ticker": "AAA", "Technical_Date": "2024-01-02"}])
    out = build_forward_returns(snap, prices(), horizons=(1,))
    row = out.iloc[0]
    assert row["Sample_Status"] == "MATURED"
    assert row["Entry_Date"] == "2024-01-03"
    assert row["Exit_Date"] == "2024-01-04"
    assert row["Forward_Return"] == 12 / 11 - 1


def test_not_matured_is_explicit():
    snap = pd.DataFrame([{"Ticker": "AAA", "Technical_Date": "2024-01-02"}])
    out = build_forward_returns(snap, prices(), horizons=(20,))
    assert out.iloc[0]["Sample_Status"] == "NOT_MATURED"
    assert out.iloc[0]["Forward_Return"] is None


def test_missing_ticker_and_signal():
    snap = pd.DataFrame([
        {"Ticker": "ZZZ", "Technical_Date": "2024-01-02"},
        {"Ticker": "AAA", "Technical_Date": "not-a-date"},
    ])
    out = build_forward_returns(snap, prices(), horizons=(1,))
    assert set(out["Sample_Status"]) == {"MISSING_PRICE"}
    assert "TICKER_NOT_IN_PRICE_PANEL" in set(out["Missing_Reason"])
    assert "INVALID_SIGNAL_DATE" in set(out["Missing_Reason"])


def test_nontrading_signal_enters_next_session():
    snap = pd.DataFrame([{"Ticker": "AAA", "Technical_Date": "2024-01-06"}])  # Saturday
    out = build_forward_returns(snap, prices(), horizons=(1,))
    assert out.iloc[0]["Entry_Date"] == "2024-01-08"


def test_invalid_price_is_missing_not_filled():
    p = prices()
    p.loc[1, "Open"] = None
    snap = pd.DataFrame([{"Ticker": "AAA", "Technical_Date": "2024-01-02"}])
    out = build_forward_returns(snap, p, horizons=(1,))
    assert out.iloc[0]["Sample_Status"] == "MISSING_PRICE"
    assert out.iloc[0]["Missing_Reason"] == "INVALID_ENTRY_OR_EXIT_PRICE"
