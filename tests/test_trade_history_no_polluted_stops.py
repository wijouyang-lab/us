#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trade_history.csv 的 Stop_Loss / Trail_Stop 不得含拼接型污染。

背景：历史上有跨 ticker 拼接（如 "跌破 255.00 美元（约-4%）"）
和 AI 长文本（如 "跌破 6.30 美元 5. 特斯拉 (TSLA) - 评分:79.8分:"）。
这些值会误导人类读者与未来的解析代码。

本测试不断言"必须数字"，因为列中有合法语义值：
- "观望"（Observation 类标记）
- "N/A"（无止损）
- "绝对规避" 等 AI 短指令（历史遗留）
- "-5%"（百分比格式止损）

这些值虽非数字，但 safe_float 会安全忽略，不构成污染。
"""
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRADE_HISTORY = REPO / "trade_history.csv"

# 拼接/长文本污染的特征子串
POLLUTION_MARKERS = [
    "(", "（",
    "评分", "诱多", "严禁", "对照组", "倒数",
    "美元", "特斯拉", "超微", "越洋",
]


def _has_pollution(v):
    s = str(v or "")
    if not s:
        return False
    if len(s) > 20:
        return True
    for m in POLLUTION_MARKERS:
        if m in s:
            return True
    return False


def test_stop_loss_columns_have_no_pollution():
    assert TRADE_HISTORY.exists()
    violations = []
    with open(TRADE_HISTORY, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            for col in ("Stop_Loss", "Trail_Stop"):
                if _has_pollution(row.get(col)):
                    violations.append((i, row.get("Date", "")[:10],
                                       row.get("Ticker", ""), col, row.get(col)))
    assert not violations, (
        f"发现 {len(violations)} 个 Stop_Loss/Trail_Stop 含污染特征：\n"
        + "\n".join(f"  line {v[0]} {v[1]} {v[2]} {v[3]}={v[4]!r}" for v in violations[:20])
    )
