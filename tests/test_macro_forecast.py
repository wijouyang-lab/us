# -*- coding: utf-8 -*-
"""宏观「预期 vs 实际」：导出层只透传 + 计算 surprise，不抓日历/不推断预期。

契约见 docs/MACRO_FORECAST_CONTRACT.md：
  · 文件缺失 → 哨兵（不注入键 → 前端隐藏）
  · 缺 forecast/actual 的条目丢弃
  · surprise = actual − forecast（pp）
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
    (d / "macro_forecast.json").write_text(
        raw if raw is not None else json.dumps(payload), encoding="utf-8")


def test_missing_returns_sentinel(tmp_path):
    assert de._read_macro_forecast(tmp_path) is de._MACRO_FORECAST_MISSING


def test_valid_computes_surprise(tmp_path):
    _write(tmp_path, {
        "schema": 1, "as_of": "2026-10-26", "source": "财经日历",
        "items": [{
            "indicator": "核心PCE物价指数", "period": "2026 Q2 · 年化季率终值",
            "forecast": 3.6, "actual": 3.3, "previous": 3.6, "unit": "%",
            "released_at": "2026-09-30", "impact": "低于预期，利好久期",
        }],
    })
    out = de._read_macro_forecast(tmp_path)
    assert out["count"] == 1
    it = out["items"][0]
    assert it["forecast"] == 3.6
    assert it["actual"] == 3.3
    assert it["surprise"] == -0.3
    assert it["impact"].startswith("低于预期")
    assert out["source"] == "财经日历"


def test_rows_missing_forecast_or_actual_dropped(tmp_path):
    _write(tmp_path, {"items": [
        {"indicator": "A", "forecast": 1.0},                 # 缺 actual
        {"indicator": "B", "actual": 2.0},                   # 缺 forecast
        {"forecast": 1.0, "actual": 1.0},                    # 缺 indicator
        {"indicator": "C", "forecast": 1.0, "actual": 1.2},  # 有效
    ]})
    out = de._read_macro_forecast(tmp_path)
    assert out["count"] == 1
    assert out["items"][0]["indicator"] == "C"
    assert out["items"][0]["surprise"] == 0.2


def test_broken_json_returns_none(tmp_path):
    _write(tmp_path, raw="{bad")
    assert de._read_macro_forecast(tmp_path) is None


def test_items_capped_at_30(tmp_path):
    _write(tmp_path, {"items": [
        {"indicator": f"I{i}", "forecast": 1.0, "actual": 1.0} for i in range(40)
    ]})
    out = de._read_macro_forecast(tmp_path)
    assert len(out["items"]) == 30
