#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 时效显示的"接线级"回归守护（静态源码断言，不 import 生产模块）。

背景：`_fmt_ai_staleness` 纯函数已有行为测试（tests/test_ai_field_fallback.py），
但**接线**（输出字段 + 前端渲染优先级）此前无守护 —— 一旦有人误删/改写这两处，
纯函数测试仍会通过，而页面上的时效标注会静默消失。本文件锁定这两条接线。

参考仓库既有静态断言范式（如 tests/test_quant_*.py 的 "无网络请求" 断言）。
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DASHBOARD = REPO / "dashboard_export.py"
APP_JS = REPO / "app.js"


def _read(p):
    assert p.exists(), f"未找到 {p}"
    return p.read_text(encoding="utf-8")


# ---------------- 1. dashboard_export.py 的输出接线 ----------------
def test_ai_score_display_wired_to_fmt_ai_staleness():
    src = _read(DASHBOARD)
    assert '"ai_score_display": _fmt_ai_staleness(' in src, (
        "dashboard_export.py 缺少 ai_score_display 的输出接线"
    )


def test_wiring_uses_ai_score_and_snapshot_update_date():
    src = _read(DASHBOARD)
    seg = "\n".join(src.split('"ai_score_display": _fmt_ai_staleness(', 1)[1].splitlines()[:3])
    assert "AI_Score" in seg, "ai_score_display 未使用 AI_Score 作为分数来源"
    assert "Snapshot_Update_Date" in seg, (
        "ai_score_display 未使用 Snapshot_Update_Date 作为更新日来源"
    )


# ---------------- 2. 纯函数存在且为模块级 ----------------
def test_fmt_ai_staleness_is_module_level():
    src = _read(DASHBOARD)
    assert "\ndef _fmt_ai_staleness(" in src, (
        "dashboard_export.py 缺少模块级 _fmt_ai_staleness 定义"
    )


# ---------------- 3. app.js 的取值接线 ----------------
def test_app_js_reads_ai_display_field():
    src = _read(APP_JS)
    assert "aiDisplay: s.ai_score_display || null," in src, (
        "app.js 未读取 ai_score_display 字段"
    )


# ---------------- 4 & 5. 渲染优先级 + 回退 ----------------
def test_ai_score_txt_prefers_display_then_falls_back():
    src = _read(APP_JS)
    line = next((l for l in src.splitlines()
                 if "#aiScoreTxt" in l and "textContent" in l), None)
    assert line is not None, "app.js 缺少 #aiScoreTxt 的 textContent 赋值"
    assert "aiDisplay" in line, "#aiScoreTxt 未使用 aiDisplay"
    assert "nv(s.s.ai, 1)" in line, "#aiScoreTxt 缺少回退到数值的逻辑"
    assert "aiDisplay != null ?" in line, "#aiScoreTxt 未体现「优先 display」的判空优先级"
