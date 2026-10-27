# -*- coding: utf-8 -*-
"""超跌观察候选：dashboard_export 只做透传与字段清洗，绝不计算分数/阈值。

本文件锁死数据契约（docs/OVERSOLD_SIGNAL_CONTRACT.md）的 fail-closed 行为：
  · 文件不存在 → 哨兵（调用方不注入键 → 前端整块隐藏）；
  · JSON 损坏 / 结构不是对象 → None（键存在但为空 → 前端空态）；
  · 正常 → ticker 大写、数值规范化、缺 ticker 的条目丢弃、最多 20 条。
"""
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import dashboard_export as de  # noqa: E402


def _write(tmp_path: Path, payload, raw: str = None):
    d = tmp_path / "dashboard" / "data"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "oversold_candidates.json"
    p.write_text(raw if raw is not None else json.dumps(payload), encoding="utf-8")
    return p


def test_missing_file_returns_sentinel(tmp_path):
    assert de._read_oversold(tmp_path) is de._OVERSOLD_MISSING


def test_valid_payload_normalized(tmp_path):
    _write(tmp_path, {
        "schema": 1,
        "generated_at": "2026-10-26T18:00:00Z",
        "asof": "2026-10-24",
        "source": "GPT 研究",
        "note": "n",
        "candidates": [{
            "ticker": "xyz", "name": "XYZ Inc", "score": "82.5", "tag": "超跌反弹",
            "rsi": "22.4", "bias_pct": "-14.2", "drawdown_pct": "-28.5",
            "ref_price": "95.2", "stop_loss": 88.5,
            "confirm": "RSI>30", "invalid": "破前低",
            "observe_until": "2026-11-05", "reason": "r",
        }],
    })
    out = de._read_oversold(tmp_path)
    assert out["count"] == 1
    c = out["candidates"][0]
    assert c["ticker"] == "XYZ"          # 统一大写
    assert c["score"] == 82.5
    assert c["rsi"] == 22.4
    assert c["bias_pct"] == -14.2
    assert c["ref_price"] == 95.2
    assert c["stop_loss"] == 88.5
    assert out["asof"] == "2026-10-24"


def test_broken_json_returns_none(tmp_path):
    _write(tmp_path, None, raw="{not json")
    assert de._read_oversold(tmp_path) is None


def test_non_object_returns_none(tmp_path):
    _write(tmp_path, [1, 2, 3])
    assert de._read_oversold(tmp_path) is None


def test_rows_without_ticker_are_dropped(tmp_path):
    _write(tmp_path, {"candidates": [
        {"ticker": "", "score": 1},
        {"name": "no ticker"},
        {"ticker": "ok", "score": 2},
        "not-a-dict",
    ]})
    out = de._read_oversold(tmp_path)
    assert out["count"] == 1
    assert out["candidates"][0]["ticker"] == "OK"


def test_candidates_capped_at_20(tmp_path):
    _write(tmp_path, {"candidates": [{"ticker": f"T{i}", "score": i} for i in range(25)]})
    out = de._read_oversold(tmp_path)
    assert out["count"] == 20
    assert len(out["candidates"]) == 20
