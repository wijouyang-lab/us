# -*- coding: utf-8 -*-
"""Tests for the non-overlapping 20D portfolio experiment."""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from nonoverlap_portfolio_backtest import schedule  # noqa: E402


def test_schedule_has_no_overlap_and_holds_20_sessions():
    dates = pd.bdate_range("2018-01-01", periods=500)
    periods = schedule(dates)
    assert len(periods) >= 20
    for a, b in zip(periods, periods[1:]):
        assert b["signal"] == a["exit"]
        assert b["entry"] > a["exit"]
    for p in periods:
        assert len(pd.bdate_range(p["entry"], p["exit"])) == 21  # entry plus 20 held sessions


def test_schedule_skips_incomplete_last_period():
    dates = pd.bdate_range("2018-01-01", periods=50)
    periods = schedule(dates)
    assert all(p["exit"] <= dates[-1] for p in periods)


def test_schedule_is_deterministic():
    dates = pd.bdate_range("2018-01-01", periods=200)
    assert schedule(dates) == schedule(dates)
