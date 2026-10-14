#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 快照陈旧告警（阶段 4）+ 盘前 AI 输入缺 Name 兜底（阶段 3 回归）。

这些断言锁定的是【渲染源码与字段契约】，不需要浏览器环境（与
tests/test_dashboard_data_stability.py 同一手法）。
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "app.js"
SCAN = REPO / "scan.py"


def test_dashboard_warns_when_ai_snapshot_is_stale():
    app = APP.read_text(encoding="utf-8")
    assert "aiStaleBanner" in app                      # 横幅 DOM id
    assert "biz" in app and "maxDate" in app   # ASCII-only anchor
    assert "notice err" in app                         # 复用现有 .notice.err 样式（未新增 CSS）
    assert "ai_status" in app and "scan_date" in app   # 读的是真实字段
    assert "partial" in app                            # 回填说明
    assert "generated_at" in app                       # 基准日期
    # 必须是「超过 2 个交易日」才告警（避免正常周末误报）
    assert re.search(r"biz\s*<=\s*2", app), "应有 2 个交易日的阈值判断"


def test_premarket_ai_input_handles_missing_name():
    """阶段 3 回归：盘前 AI 输入字段必须 .get 兜底，绝无硬索引。"""
    src = SCAN.read_text(encoding="utf-8")
    assert '_name = x.get("Name", "N/A")' in src
    assert '_price = x.get("Price", "N/A")' in src
    assert "x['Name']" not in src and 'x["Name"]' not in src
