# -*- coding: utf-8 -*-
"""Tests for delisted recovery validation; no network."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import delisted_recovery_validator as v  # noqa: E402


def frame(start, end):
    idx = pd.bdate_range(start, end)
    return pd.DataFrame({"Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 10.5,
                         "Volume": 100}, index=idx)


def test_pre_delisting_series_accepted():
    out = v.validate_delisted_frame(frame("2000-01-03", "2007-10-26"), date(2007, 10, 26))
    assert out["accepted"] is True
    assert out["last"] == "2007-10-26"


def test_ticker_reuse_starting_after_delisting_rejected():
    out = v.validate_delisted_frame(frame("2020-01-02", "2025-01-02"), date(2007, 10, 26))
    assert out["accepted"] is False
    assert "series_starts_after_delisting_ticker_reuse" in out["reasons"]


def test_series_extending_after_delisting_rejected():
    out = v.validate_delisted_frame(frame("2000-01-03", "2020-01-02"), date(2007, 10, 26))
    assert "series_extends_after_delisting_ticker_reuse" in out["reasons"]


def test_series_ending_too_early_rejected():
    out = v.validate_delisted_frame(frame("2000-01-03", "2006-01-02"), date(2007, 10, 26))
    assert "series_ends_too_early" in out["reasons"]


def test_invalid_ohlc_rejected():
    f = frame("2000-01-03", "2007-10-26")
    f.loc[f.index[0], "High"] = 1.0
    out = v.validate_delisted_frame(f, date(2007, 10, 26))
    assert "invalid_ohlc" in out["reasons"]
