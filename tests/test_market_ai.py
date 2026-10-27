# -*- coding: utf-8 -*-
"""市场情绪 AI 解读：dashboard_export 只透传外部文本，不调用任何 AI。

契约：dashboard/data/market_ai_commentary.json
  {"generated_at": "...", "model": "...", "summary": "...",
   "sections": [{"title": "...", "text": "..."}]}
fail-closed：文件缺失 → 哨兵（不注入键 → 前端 pending）；损坏/非对象 → None。
"""
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import dashboard_export as de  # noqa: E402


def _write(tmp_path: Path, payload=None, raw=None):
    d = tmp_path / "dashboard" / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "market_ai_commentary.json").write_text(
        raw if raw is not None else json.dumps(payload), encoding="utf-8")


def test_missing_returns_sentinel(tmp_path):
    assert de._read_market_ai(tmp_path) is de._MARKET_AI_MISSING


def test_valid_payload_normalized(tmp_path):
    _write(tmp_path, {
        "generated_at": "2026-10-27T00:00:00Z",
        "model": "gpt-x",
        "summary": " 整体偏恐慌 ",
        "sections": [
            {"title": "F&G", "text": " 六个子项都弱 "},
            {"title": "空段", "text": "   "},        # 空文本丢弃
            "not-a-dict",                            # 非对象丢弃
            {"title": "", "text": "无标题段落"},
        ],
    })
    out = de._read_market_ai(tmp_path)
    assert out["summary"] == "整体偏恐慌"
    assert out["model"] == "gpt-x"
    assert [s["text"] for s in out["sections"]] == ["六个子项都弱", "无标题段落"]
    assert out["sections"][1]["title"] is None


def test_sections_capped_at_10(tmp_path):
    _write(tmp_path, {"sections": [{"text": f"T{i}"} for i in range(15)]})
    out = de._read_market_ai(tmp_path)
    assert len(out["sections"]) == 10


def test_broken_json_returns_none(tmp_path):
    _write(tmp_path, raw="{bad")
    assert de._read_market_ai(tmp_path) is None


def test_non_object_returns_none(tmp_path):
    _write(tmp_path, ["x"])
    assert de._read_market_ai(tmp_path) is None
