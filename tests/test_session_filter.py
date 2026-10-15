#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""23/5 交易防御：_filter_regular_session 的会话时段过滤测试。"""
import ast
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load():
    src = (REPO / "review.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == "_filter_regular_session":
            ns = {}
            exec(ast.get_source_segment(src, node), ns)
            return ns["_filter_regular_session"]
    raise AssertionError("_filter_regular_session not found in review.py")


def _df(index):
    return pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0},
                        index=pd.DatetimeIndex(index))


def test_pure_date_index_is_noop():
    f = _load()
    df = _df(["2026-10-13", "2026-10-14"])
    got = f(df)
    assert len(got) == 2


def test_overnight_bars_filtered():
    f = _load()
    df = _df(["2026-10-14 09:31", "2026-10-14 12:00", "2026-10-14 15:59",
              "2026-10-14 21:00", "2026-10-15 02:00", "2026-10-15 04:30"])
    got = f(df)
    assert len(got) == 3
    assert all(datetime(2026, 10, 14, 9, 30) <= t <= datetime(2026, 10, 14, 16, 0)
               for t in got.index)


def test_empty_df_ok():
    f = _load()
    assert len(f(_df([]))) == 0


def test_non_datetime_index_is_noop():
    f = _load()
    df = pd.DataFrame({"Open": [1.0], "Close": [1.0]}, index=["not-a-timestamp"])
    got = f(df)
    assert len(got) == 1


def test_regular_hours_preserved():
    f = _load()
    df = _df(["2026-10-14 09:30", "2026-10-14 16:00"])
    assert len(f(df)) == 2
