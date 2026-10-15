#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日候选因子快照 _persist_candidate_snapshots 的行为测试。"""
import ast
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_SRC = (REPO / "scan.py").read_text(encoding="utf-8")


def _load(tmp_path, monkeypatch):
    """ast 抽取函数，并把 CANDIDATE_SNAPSHOT_FILE 指向临时文件。"""
    target = tmp_path / "candidate_factor_snapshots.csv"
    for node in ast.parse(_SRC).body:
        if isinstance(node, ast.FunctionDef) and node.name == "_persist_candidate_snapshots":
            ns = {"CANDIDATE_SNAPSHOT_FILE": str(target)}
            exec(ast.get_source_segment(_SRC, node), ns)
            return ns["_persist_candidate_snapshots"], target
    raise AssertionError("_persist_candidate_snapshots not found in scan.py")


COLS = ["Date", "Ticker", "Tag", "Final_Score", "Quant_Score", "AI_Score",
        "RSI", "MACD", "ATR_Pct", "MA20", "MA50", "Price", "Market_Regime"]


def _rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_empty_candidates_writes_nothing(tmp_path):
    f, target = _load(tmp_path, None)
    f([], "2026-10-15")
    f(None, "2026-10-15")
    assert not target.exists(), "空候选不应创建文件"


def test_first_call_writes_header_and_row(tmp_path):
    f, target = _load(tmp_path, None)
    f([{"Ticker": "ADSK", "Tag": "Core_Dragon", "Quant_Score": 70}], "2026-10-15")
    lines = target.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].split(",") == COLS, "表头不正确"
    assert len(lines) == 2
    r = _rows(target)[0]
    assert r["Date"] == "2026-10-15" and r["Ticker"] == "ADSK"
    assert r["Tag"] == "Core_Dragon" and r["Quant_Score"] == "70"


def test_second_call_appends_without_duplicate_header(tmp_path):
    f, target = _load(tmp_path, None)
    f([{"Ticker": "ADSK"}], "2026-10-15")
    f([{"Ticker": "KR"}], "2026-10-16")
    rows = _rows(target)
    assert len(rows) == 2
    assert [r["Ticker"] for r in rows] == ["ADSK", "KR"]
    assert target.read_text(encoding="utf-8").count("Date,Ticker,Tag") == 1


def test_missing_fields_become_empty_strings(tmp_path):
    f, target = _load(tmp_path, None)
    f([{"Ticker": "ADSK"}], "2026-10-15")
    r = _rows(target)[0]
    for c in COLS:
        assert c in r, f"缺列 {c}"
    assert r["AI_Score"] == "" and r["MA50"] == "" and r["Market_Regime"] == ""


def test_key_fields_mapped_correctly(tmp_path):
    f, target = _load(tmp_path, None)
    f([{"ticker": "kr", "tag": "Observation", "Final_Score": 88.5, "AI_Score": 77,
        "RSI": 55.2, "MACD": "金叉", "ATR_Pct": 3.1, "MA20": 10.5, "MA50": 9.8,
        "Close_Price": 12.3, "Market_Regime": "HAWKISH"},
       {"Ticker": "ADSK", "Price": 250.0}], "2026-10-15")
    rows = _rows(target)
    r0, r1 = rows[0], rows[1]
    assert r0["Ticker"] == "kr" and r0["Tag"] == "Observation"
    assert r0["Final_Score"] == "88.5" and r0["AI_Score"] == "77"
    assert r0["MACD"] == "金叉" and r0["Market_Regime"] == "HAWKISH"
    assert r0["Price"] == "12.3", "Close_Price 兜底未生效"
    assert r1["Price"] == "250.0", "Price 直取未生效"
