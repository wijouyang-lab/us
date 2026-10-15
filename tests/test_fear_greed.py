#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CNN Fear & Greed 条目构造 _fetch_fear_greed 的回归测试（mock 库，不联网）。"""
import ast
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load():
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == "_fetch_fear_greed":
            ns = {"datetime": __import__("datetime")}
            exec(ast.get_source_segment(src, node), ns)
            return ns["_fetch_fear_greed"]
    raise AssertionError("_fetch_fear_greed not found in scan.py")


def _fake_module(get_impl):
    mod = types.ModuleType("fear_greed")
    mod.get = get_impl
    return mod


def _with(monkeypatch, get_impl):
    monkeypatch.setitem(sys.modules, "fear_greed", _fake_module(get_impl))


def test_normal_returns_seven_fields(monkeypatch):
    _with(monkeypatch, lambda: {"score": 64.0, "rating": "Greed", "history": {"1w": 60.0}})
    got = _load()()
    assert set(got.keys()) == {"indicator", "value", "prev", "date", "source",
                               "sentiment", "rationale"}
    assert got["indicator"] == "Fear & Greed"
    assert got["value"] == "64 (Greed)"
    assert got["source"] == "CNN"


def test_rating_fear_is_bearish(monkeypatch):
    _with(monkeypatch, lambda: {"score": 20.0, "rating": "Fear", "history": {"1w": 25.0}})
    assert _load()()["sentiment"] == "bearish"


def test_rating_greed_is_bullish(monkeypatch):
    _with(monkeypatch, lambda: {"score": 70.0, "rating": "Greed", "history": {}})
    assert _load()()["sentiment"] == "bullish"


def test_rating_neutral_is_neutral(monkeypatch):
    _with(monkeypatch, lambda: {"score": 50.0, "rating": "Neutral", "history": {}})
    assert _load()()["sentiment"] == "neutral"


def test_get_raises_returns_none(monkeypatch):
    def boom():
        raise RuntimeError("network down")
    _with(monkeypatch, boom)
    assert _load()() is None


def test_import_error_returns_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "fear_greed", None)   # import 失败
    assert _load()() is None


def test_rationale_is_none(monkeypatch):
    _with(monkeypatch, lambda: {"score": 64.0, "rating": "Greed", "history": {}})
    assert _load()()["rationale"] is None


def test_prev_from_history_1w(monkeypatch):
    _with(monkeypatch, lambda: {"score": 64.0, "rating": "Greed", "history": {"1w": 60.0}})
    assert _load()()["prev"] == "60"
    _with(monkeypatch, lambda: {"score": 64.0, "rating": "Greed", "history": {}})
    assert _load()()["prev"] is None
