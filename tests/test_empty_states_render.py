# -*- coding: utf-8 -*-
"""空态统一 + 移动端：静态契约检查（避免依赖 DOM 桩）。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_empty_state_helper_and_usage():
    src = (ROOT / "app.js").read_text(encoding="utf-8")
    assert "function emptyState" in src
    assert "emptyState('na', '暂无新闻" in src
    assert "emptyState('na', '暂无经济数据')" in src


def test_empty_state_css_and_mobile():
    css = (ROOT / "app.css").read_text(encoding="utf-8")
    assert ".es{display:flex" in css
    assert ".es-err" in css
    assert "@media (max-width: 640px)" in css
