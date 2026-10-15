#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-2：保本线 _apply_breakeven_floor 的行为测试。

review.py 无 __main__ 守卫，无法直接 import，故 ast 抽取该纯函数。
"""
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load_fn():
    src = (REPO / "review.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    ns = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_apply_breakeven_floor":
            exec(ast.get_source_segment(src, node), ns)
            return ns["_apply_breakeven_floor"]
    raise AssertionError("_apply_breakeven_floor 未找到")


def test_below_trigger_returns_candidate():
    f = _load_fn()
    assert f(95, 100, 104, 5.0, 1.0) == 95


def test_at_trigger_returns_max_of_candidate_and_entry():
    f = _load_fn()
    assert f(95, 100, 105, 5.0, 1.0) == 100


def test_above_trigger_candidate_below_entry():
    f = _load_fn()
    assert f(95, 100, 110, 5.0, 1.0) == 100


def test_above_trigger_candidate_above_entry_no_downgrade():
    f = _load_fn()
    assert f(108, 100, 110, 5.0, 1.0) == 108


def test_none_entry_returns_candidate():
    f = _load_fn()
    assert f(95, None, 110, 5.0, 1.0) == 95


def test_zero_or_negative_entry_returns_candidate():
    f = _load_fn()
    assert f(95, 0, 110, 5.0, 1.0) == 95
    assert f(95, -10, 110, 5.0, 1.0) == 95


def test_none_close_returns_candidate():
    f = _load_fn()
    assert f(95, 100, None, 5.0, 1.0) == 95


def test_floor_multiplier_above_one():
    f = _load_fn()
    assert f(95, 100, 110, 5.0, 1.02) == 102


def test_non_numeric_returns_candidate():
    f = _load_fn()
    assert f(95, "N/A", 110, 5.0, 1.0) == 95
    assert f(95, 100, "N/A", 5.0, 1.0) == 95
