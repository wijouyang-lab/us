# -*- coding: utf-8 -*-
"""Regression tests for yfinance daily session-date normalization in scan.py."""
from __future__ import annotations

import ast
import datetime
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from us_market_calendar import last_completed_regular_session

REPO = Path(__file__).resolve().parents[1]
SCAN = REPO / "scan.py"
US_TZ = ZoneInfo("America/New_York")


def _load_scan_date_functions():
    source = SCAN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"_last_completed_regular_date_us", "_filter_completed_daily_bars"}
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    assert {node.name for node in nodes} == wanted
    namespace = {"pd": pd, "datetime": datetime, "US_TZ": US_TZ, "last_completed_regular_session": last_completed_regular_session}
    for node in nodes:
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SCAN), "exec"), namespace)
    return namespace["_filter_completed_daily_bars"]


def test_naive_daily_session_labels_are_not_shifted_to_previous_day():
    filter_bars = _load_scan_date_functions()
    # yfinance daily indices are often tz-naive exchange-session labels.
    df = pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.DatetimeIndex(["2026-10-16", "2026-10-19"]),
    )
    monday_premarket = datetime.datetime(2026, 10, 19, 9, 0, tzinfo=US_TZ)
    result = filter_bars(df, monday_premarket)
    assert list(result["Close"]) == [100.0]
    assert result.index[0].strftime("%Y-%m-%d") == "2026-10-16"
    assert result.index[0].date().weekday() == 4


def test_completed_same_day_bar_is_kept_after_regular_close():
    filter_bars = _load_scan_date_functions()
    df = pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.DatetimeIndex(["2026-10-16", "2026-10-19"]),
    )
    monday_after_close = datetime.datetime(2026, 10, 19, 16, 30, tzinfo=US_TZ)
    result = filter_bars(df, monday_after_close)
    assert list(result["Close"]) == [100.0, 101.0]
    assert result.index[-1].strftime("%Y-%m-%d") == "2026-10-19"


def test_timezone_aware_intrinsic_timestamp_is_converted_to_new_york():
    filter_bars = _load_scan_date_functions()
    utc_idx = pd.DatetimeIndex(["2026-10-19 13:30:00+00:00", "2026-10-19 20:00:00+00:00"])
    df = pd.DataFrame({"Close": [100.0, 101.0]}, index=utc_idx)
    monday_after_close = datetime.datetime(2026, 10, 19, 16, 30, tzinfo=US_TZ)
    result = filter_bars(df, monday_after_close)
    assert list(result["Close"]) == [100.0, 101.0]
    assert all(ts.strftime("%Y-%m-%d") == "2026-10-19" for ts in result.index)


if __name__ == "__main__":
    tests = [
        test_naive_daily_session_labels_are_not_shifted_to_previous_day,
        test_completed_same_day_bar_is_kept_after_regular_close,
        test_timezone_aware_intrinsic_timestamp_is_converted_to_new_york,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Result: {len(tests)}/{len(tests)} passed")
