#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPI 同比自算函数 _calc_yoy_from_series 的回归测试。

scan.py 无法直接 import（模块级副作用），故 ast 抽取纯函数。
"""
import ast
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load(name):
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            ns = {}
            exec(ast.get_source_segment(src, node), ns)
            return ns[name]
    raise AssertionError(f"{name} not found in scan.py")


def _series(values, start_year=2025, start_month=1):
    out, y, m = [], start_year, start_month
    for v in values:
        out.append((datetime(y, m, 1), float(v)))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def test_normal_13_periods():
    f = _load("_calc_yoy_from_series")
    vals = [100.0] * 12 + [103.0]          # 去年同期 100，最新 103
    got = f(_series(vals))
    assert got is not None and abs(got - 3.0) < 1e-9


def test_insufficient_periods_returns_none():
    f = _load("_calc_yoy_from_series")
    assert f(_series([100.0] * 12)) is None      # 只有 12 期 < 13
    assert f(_series([100.0] * 5)) is None


def test_empty_returns_none():
    f = _load("_calc_yoy_from_series")
    assert f([]) is None
    assert f(None) is None


def test_zero_base_returns_none():
    f = _load("_calc_yoy_from_series")
    vals = [0.0] + [100.0] * 12                  # 去年同期 = 0
    assert f(_series(vals)) is None
    vals2 = [-5.0] + [100.0] * 12                # 负基数
    assert f(_series(vals2)) is None


def test_periods_back_one():
    f = _load("_calc_yoy_from_series")
    vals = [200.0, 210.0]
    got = f(_series(vals), periods_back=1)
    assert got is not None and abs(got - 5.0) < 1e-9
