#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 保留 + 时效分级的回归测试。

dashboard_export.py 无法直接 import（模块级副作用），故 ast 抽取纯函数。
"""
import ast
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load(name):
    src = (REPO / "dashboard_export.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            ns = {}
            exec(ast.get_source_segment(src, node), ns)
            return ns[name]
    raise AssertionError(f"{name} not found")


# ---------------- A. _resolve_hist_ai_score ----------------
def test_hist_single_row():
    f = _load("_resolve_hist_ai_score")
    assert f([{"Ticker": "ADSK", "Date": "2026-10-07", "AI_Score": "44.0"}], "ADSK") == "44.0"


def test_hist_picks_latest_date():
    f = _load("_resolve_hist_ai_score")
    rows = [{"Ticker": "ADSK", "Date": "2026-10-07", "AI_Score": "44.0"},
            {"Ticker": "ADSK", "Date": "2026-10-14", "AI_Score": "55.5"},
            {"Ticker": "ADSK", "Date": "2026-09-01", "AI_Score": "30.0"}]
    assert f(rows, "ADSK") == "55.5"


def test_hist_no_match_returns_empty():
    f = _load("_resolve_hist_ai_score")
    assert f([{"Ticker": "AAA", "Date": "2026-10-07", "AI_Score": "44.0"}], "ADSK") == ""


def test_hist_all_empty_returns_empty():
    f = _load("_resolve_hist_ai_score")
    rows = [{"Ticker": "ADSK", "Date": "2026-10-07", "AI_Score": ""},
            {"Ticker": "ADSK", "Date": "2026-10-14", "AI_Score": "   "}]
    assert f(rows, "ADSK") == ""
    assert f([], "ADSK") == ""
    assert f([{"Ticker": "ADSK", "Date": "2026-10-07"}], "ADSK") == ""


# ---------------- B. _fmt_ai_staleness ----------------
def test_staleness_none_score():
    assert _load("_fmt_ai_staleness")(None, "2026-10-14") is None


def test_staleness_fresh():
    f = _load("_fmt_ai_staleness")
    today = datetime.now().date().strftime("%Y-%m-%d")
    assert f(44, today) == f"44（{today}）"


def test_staleness_warning_8_days():
    f = _load("_fmt_ai_staleness")
    d8 = (datetime.now().date() - timedelta(days=8)).strftime("%Y-%m-%d")
    assert f(44, d8) == f"44（{d8}）\u26a0\ufe0f"


def test_staleness_paused_13_days():
    f = _load("_fmt_ai_staleness")
    d13 = (datetime.now().date() - timedelta(days=13)).strftime("%Y-%m-%d")
    assert f(44, d13) == f"44（{d13}）\u23f8"


def test_staleness_expired_20_days():
    f = _load("_fmt_ai_staleness")
    d20 = (datetime.now().date() - timedelta(days=20)).strftime("%Y-%m-%d")
    assert f(44, d20) == f"AI 数据已过期（最后 {d20}）"


def test_staleness_no_date():
    assert _load("_fmt_ai_staleness")(44, None) == "44"
    assert _load("_fmt_ai_staleness")(44, "bad-date") == "44"


# ---------------- C. texts 空串键过滤 ----------------
def test_texts_filters_empty_keys():
    texts = {"k1": "v1", "k2": "", "k3": None}
    merged = dict({"snapshot_id": "s1"})
    merged.update({k: v for k, v in texts.items() if v})
    assert merged == {"snapshot_id": "s1", "k1": "v1"}


# ---------------- D. G2b' 修正（复刻逻辑） ----------------
def _g2b(rec_date, exact_snap, snapshots, key):
    snap = exact_snap
    snap_used_date = rec_date
    _cands = [(k[1], v) for k, v in snapshots.items() if k[0] == key[0] and k[2] == key[2]]
    if _cands:
        _cands.sort(key=lambda x: str(x[0]), reverse=True)
        for _d, _sn in _cands:
            if str(_d) <= str(rec_date):
                break
            _texts = _sn.get("texts") or {}
            if any(_texts.values()):
                snap = _sn
                snap_used_date = _d
                break
    return snap, snap_used_date


KEY = ("ADSK", "2026-10-07", "Core_Dragon")


def test_g2b_uses_newer_nonempty():
    exact = {"id": "old", "texts": {"a": "old"}}
    newer = {"id": "new", "texts": {"a": "new"}}
    sn, d = _g2b("2026-10-07", exact, {KEY: exact, ("ADSK", "2026-10-14", "Core_Dragon"): newer}, KEY)
    assert sn is newer and d == "2026-10-14"


def test_g2b_skips_newer_all_empty():
    exact = {"id": "old", "texts": {"a": "old"}}
    empty_newer = {"id": "new", "texts": {"a": "", "b": None}}
    sn, d = _g2b("2026-10-07", exact, {KEY: exact, ("ADSK", "2026-10-14", "Core_Dragon"): empty_newer}, KEY)
    assert sn is exact and d == "2026-10-07"


def test_g2b_no_newer_keeps_exact():
    exact = {"id": "old", "texts": {"a": "old"}}
    sn, d = _g2b("2026-10-07", exact, {KEY: exact}, KEY)
    assert sn is exact and d == "2026-10-07"
