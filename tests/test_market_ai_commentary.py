# -*- coding: utf-8 -*-
"""市场情绪 AI 解读生成器：提示词/解析/落盘/fail-closed 测试（不联网）。

覆盖：
  · 提示词只包含指标文件里的真实数字；
  · 模型输出 JSON 的清洗与校验；
  · --offline 回放可写出符合契约的文件（_read_market_ai 可读）；
  · 无指标数据 → exit 0 且不写文件；
  · 模型输出非法 → exit 1 且**不覆盖**旧文件；
  · --dry-run 不落盘。
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(_REPO_ROOT))

import dashboard_export as de  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "market_ai_commentary", _REPO_ROOT / "dashboard" / "market_ai_commentary.py")
mac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mac)

IND = {
    "fear_greed": {
        "score": 27.08, "rating": "fear",
        "timestamp": "2026-10-27T00:00:00+00:00",
        "subindicators": {
            "safe_haven_demand": {"score": 11.0, "rating": "extreme fear"},
            "put_call_options": {"score": 22.8, "rating": "extreme fear"},
        },
        "history_30d": [{"date": "2026-10-27", "score": 27.08},
                        {"date": "2026-10-22", "score": 19.44}],
    },
    "fedwatch": {
        "next_meeting": "2026-10-28", "current_target": "3.75%-4.00%",
        "effr": 3.88, "trade_date": "2026-10-26",
        "meetings": [{"date": "2026-10-28",
                      "probabilities": {"hold": 88.9, "hike_25bp": 11.1}}],
    },
    "error": None,
}


def _write_indicators(tmp_path: Path, payload=IND) -> Path:
    p = tmp_path / "market_indicators.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _write_model_output(tmp_path: Path, payload) -> Path:
    p = tmp_path / "model.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_normalize_valid():
    out = mac.normalize_model_payload({
        "summary": " 总述 ",
        "sections": [{"title": " A ", "text": " 正文 "}, {"title": "空", "text": "  "}, "x"],
    })
    assert out["summary"] == "总述"
    assert out["sections"] == [{"title": "A", "text": "正文"}]


def test_normalize_invalid():
    assert mac.normalize_model_payload({"summary": "", "sections": []}) is None
    assert mac.normalize_model_payload("not-a-dict") is None


def test_prompt_contains_real_numbers():
    msgs = mac.build_prompt(IND)
    text = "\n".join(m["content"] for m in msgs)
    assert "27.08" in text
    assert "11.0" in text and "极度恐惧" in text
    assert "88.9" in text and "2026-10-28" in text
    assert "3.75%-4.00%" in text
    assert "JSON" in text


def test_offline_write_matches_contract(tmp_path):
    ind = _write_indicators(tmp_path)
    model = _write_model_output(tmp_path, {
        "summary": "恐惧区间，防御为主。",
        "sections": [{"title": "情绪", "text": "总分 27.08，避险需求 11.0。"}],
    })
    out = tmp_path / "dashboard" / "data" / "market_ai_commentary.json"
    rc = mac.main(["--indicators", str(ind), "--out", str(out),
                   "--offline", "--input-json", str(model), "--model", "test-model"])
    assert rc == 0
    parsed = de._read_market_ai(tmp_path)
    assert parsed["summary"] == "恐惧区间，防御为主。"
    assert parsed["model"] == "test-model"
    assert parsed["sections"][0]["title"] == "情绪"


def test_missing_indicators_exits_zero(tmp_path):
    out = tmp_path / "o.json"
    rc = mac.main(["--indicators", str(tmp_path / "missing.json"), "--out", str(out)])
    assert rc == 0
    assert not out.exists()


def test_bad_model_output_keeps_old_file(tmp_path):
    ind = _write_indicators(tmp_path)
    out = tmp_path / "o.json"
    out.write_text('{"summary":"旧内容"}', encoding="utf-8")
    bad = _write_model_output(tmp_path, {"foo": "bar"})
    rc = mac.main(["--indicators", str(ind), "--out", str(out),
                   "--offline", "--input-json", str(bad)])
    assert rc == 1
    assert out.read_text(encoding="utf-8") == '{"summary":"旧内容"}'


def test_dry_run_does_not_write(tmp_path):
    ind = _write_indicators(tmp_path)
    model = _write_model_output(tmp_path, {"summary": "S", "sections": []})
    out = tmp_path / "o.json"
    rc = mac.main(["--indicators", str(ind), "--out", str(out), "--dry-run",
                   "--offline", "--input-json", str(model)])
    assert rc == 0
    assert not out.exists()
