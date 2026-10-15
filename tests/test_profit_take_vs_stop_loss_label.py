#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1：移动止盈 vs 静态止损 的状态判定（_classify_exit_status）行为级测试。"""
import ast
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load_classifier():
    """scan/review 无法直接 import（无 __main__ 守卫），故 ast 抽取该纯函数。"""
    src = (REPO / "review.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    ns = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_classify_exit_status":
            exec(ast.get_source_segment(src, node), ns)
            return ns["_classify_exit_status"]
    raise AssertionError("_classify_exit_status 未找到")


def test_profit_take_when_exit_above_entry():
    assert _load_classifier()(205.00, 200.00) == "Trailing_Profit_Take"


def test_stop_loss_when_exit_below_entry():
    assert _load_classifier()(195.00, 200.00) == "Stop_Loss_Hit"


def test_equal_prices_is_stop_loss_not_profit_take():
    """等值不算止盈（fail-safe）。"""
    assert _load_classifier()(200.00, 200.00) == "Stop_Loss_Hit"


def test_none_exit_price_falls_back_to_stop_loss():
    assert _load_classifier()(None, 200.00) == "Stop_Loss_Hit"


def test_none_rec_price_falls_back_to_stop_loss():
    assert _load_classifier()(205.00, None) == "Stop_Loss_Hit"


def test_non_numeric_falls_back_to_stop_loss():
    assert _load_classifier()("N/A", 200.00) == "Stop_Loss_Hit"


def test_string_numbers_are_supported():
    assert _load_classifier()("205.00", "200.00") == "Trailing_Profit_Take"


def test_real_world_case_kr_and_isrg():
    """实测案例：KR 60.68 > 59.27 应为止盈；ISRG 414.81 > 405.07 应为止盈。"""
    f = _load_classifier()
    assert f(60.68, 59.27) == "Trailing_Profit_Take"     # KR
    assert f(414.81, 405.07) == "Trailing_Profit_Take"   # ISRG
    assert f(204.97999572753906, 211.30) == "Stop_Loss_Hit"   # ANET（真止损）


def test_new_status_registered_in_closed_sets():
    """集成契约：新状态必须被各处「已关闭/终态」集合识别。"""
    checks = {
        "review.py": ("CLOSED_STOCK_STATUSES = {", '"Trailing_Profit_Take"'),
        "portfolio_50000.py": ("TERMINAL_STATUSES = {", '"Trailing_Profit_Take"'),
        "dashboard_export.py": ("CLOSED_STOCK_STATUSES = {", '"Trailing_Profit_Take"'),
    }
    for fname, (open_line, needle) in checks.items():
        src = (REPO / fname).read_text(encoding="utf-8")
        blk = src.split(open_line, 1)[1].split("}", 1)[0]
        assert needle in blk, "%s 的集合缺少新状态" % fname


def test_inline_closed_set_in_review_has_new_status():
    """review.py 的内联集合（历史事件退出价分支）也要含新状态。"""
    src = (REPO / "review.py").read_text(encoding="utf-8")
    seg = src.split('if status in {', 1)[1].split('} and exit_price is not None', 1)[0]
    assert '"Trailing_Profit_Take"' in seg


def test_stop_loss_hit_count_set_unchanged():
    """按裁决：stop_loss_hit_count 的集合不得包含新状态（保持语义纯净）。"""
    src = (REPO / "dashboard_export.py").read_text(encoding="utf-8")
    seg = src.split('"stop_loss_hit_count": sum(', 1)[1].split("),", 1)[0]
    assert "Trailing_Profit_Take" not in seg
