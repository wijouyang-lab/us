# -*- coding: utf-8 -*-
"""端到端（离线）：导出层 reader → payload → 前端渲染关键区块。

不联网：用临时目录构造 dashboard/data/*.json，调用 dashboard_export 的
_read_* 读取器组装 payload，再用真实 app.js 渲染并断言关键文案。
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dashboard_export as de  # noqa: E402


def _front():
    spec = importlib.util.spec_from_file_location(
        "front", ROOT / "tests" / "test_profit_taken_frontend.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write(tmp_path: Path, rel: str, payload):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


def test_export_readers_flow_into_rendered_sections(tmp_path):
    _write(tmp_path, "dashboard/data/macro_indicators.json", {
        "schema": 1, "ok": 2, "items": [
            {"key": "unrate", "name": "美国失业率", "value": 4.2, "unit": "%",
             "date": "2026-09-01", "prev": 4.1, "change": 0.1,
             "source": "FRED UNRATE", "source_status": "primary"},
            {"key": "cpi_yoy", "name": "未季调CPI年率", "value": 3.7, "unit": "%",
             "date": "2026-09-01", "prev": 3.4, "change": 0.3,
             "source": "TradingEconomics", "source_status": "fallback"},
        ]})
    _write(tmp_path, "dashboard/data/macro_forecast.json", {
        "schema": 1, "source": "自动", "items": [
            {"indicator": "CPI 同比", "period": "2026年9月", "forecast": 3.6,
             "actual": 3.7, "previous": 3.4, "unit": "%", "surprise": 0.1,
             "impact": "高于预期"}],
    })
    _write(tmp_path, "dashboard/data/macro_cpi_ai.json", {
        "signature": "x", "model": "deepseek-flash",
        "analysis": "CPI 高于预期，利率预期上修。",
    })
    _write(tmp_path, "dashboard/data/oversold_candidates.json", {
        "schema": 1, "asof": "2026-10-27", "ai_count": 1,
        "candidates": [{
            "ticker": "AAA", "sector": "Technology", "score": 60, "rsi": 22,
            "bias_pct": -15, "drawdown_pct": -20, "ref_price": 50,
            "stop_loss": 46,
            "ai": {"verdict": "关注", "technical": "RSI 22 超卖",
                   "fundamental": "PE 20x", "news": "财报超预期",
                   "risk": "板块同步下跌"},
        }]})
    _write(tmp_path, "dashboard/data/skill_serenity.json", {
        "schema_version": 2, "mode": "offline_screening", "skill_version": "1.1.0",
        "asof": "2026-10-25",
        "priorities": [{"ticker": "EOG", "priority_rank": 1,
                        "why": "供应链瓶颈", "what_to_verify": "客户集中度"}],
    })
    _write(tmp_path, "dashboard/data/serenity_verified.json", {
        "schema": 1, "count": 1, "items": [{
            "ticker": "EOG", "earnings_date": "2026-11-05",
            "filings": [{"form": "8-K", "date": "2026-10-08", "url": "https://www.sec.gov/x"}],
            "news": [], "missing": ["新闻"], "status": "verified",
        }]})

    payload = {
        "portfolio": {"positions": [], "target": [], "transactions": []},
        "macro": {"generated_at": "x", "economic": [], "speakers": []},
    }
    for key, reader in (
        ("macro_indicators", de._read_macro_indicators),
        ("macro_forecast", de._read_macro_forecast),
        ("macro_cpi_ai", de._read_macro_cpi_ai),
        ("oversold", de._read_oversold),
        ("skill_serenity", de._read_skill_serenity),
        ("serenity_verified", de._read_serenity_verified),
    ):
        got = reader(tmp_path)
        if got is not None and got.__class__.__name__ != "object":
            payload[key] = got

    out = _front()._run(payload)

    macro = out["macro"] or ""
    assert "美国失业率" in macro and "4.20%" in macro
    assert "预期" in macro and "3.60%" in macro and "3.70%" in macro
    assert "兜底源" in macro
    assert "CPI 高于预期" in macro

    ov = out["oversold"] or ""
    assert "AI 综合" in ov and "关注" in ov and "RSI 22 超卖" in ov

    sk = out["serenity"] or ""
    assert "EOG" in sk and "🎯" in sk
    assert "核验" in sk and "8-K" in sk and "2026-11-05" in sk
