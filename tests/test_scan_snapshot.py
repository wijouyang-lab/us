#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方案 A：持仓每日 AI 快照持久化（含源码契约 + 落盘行为）。"""
import ast
import csv
import os
import tempfile

import pytest

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAN = REPO / "scan.py"


def _lines():
    return (SCAN.read_text(encoding="utf-8")).splitlines()


def _ln(pat):
    for i, l in enumerate(_lines(), 1):
        if pat in l:
            return i
    return -1


def test_holdings_persisted_without_new_recommendations():
    """F3 契约：持久化输入取自 enrich 产物（含持仓），不再取自 to_write。"""
    src = SCAN.read_text(encoding="utf-8")
    assert "_ai_persist_source = list(_enriched)" in src
    assert "_ai_persist = list(_ai_persist_source)" in src
    assert "_ai_persist = list(to_write)" not in src      # 旧捕获点已移除
    assert "upsert_ai_text_cache(_ai_persist)" in src
    assert "upsert_ai_snapshot(_ai_persist, rec_date=today_us_str())" in src



def test_no_write_when_no_holdings_no_recommendations():
    """无持仓且无推荐 -> enrich 产物为空 -> if _ai_persist: 短路（不误写）。"""
    src = SCAN.read_text(encoding="utf-8")
    assert "if _ai_persist:" in src
    tail = src.split("if _ai_persist:", 1)[1]
    assert "upsert_ai_text_cache(_ai_persist)" in tail
    assert "upsert_ai_snapshot(_ai_persist, rec_date=today_us_str())" in tail

