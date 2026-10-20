from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCAN = REPO / "scan.py"


def _source() -> str:
    return SCAN.read_text(encoding="utf-8")


def test_ai_matcher_and_field_normalizer_are_wired():
    src = _source()
    assert "from scripts.ai_item_matching import match_ai_rows, normalize_ai_fields" in src
    assert "match_ai_rows(items, rows)" in src
    assert "normalize_ai_fields(by_ticker.get(ticker,{}))" in src


def test_json_structure_failures_are_logged_without_raw_model_output():
    src = _source()
    assert "[AI解释层结构诊断]" in src
    assert "JSON根对象解析失败或不是对象" in src
    assert "顶层 items 不是数组" in src
    assert "items 数组为空" in src
    # Avoid accidentally adding logs that dump the complete prompt or model answer.
    assert "print(txt)" not in src
    assert "print(prompt)" not in src


def test_missing_tickers_and_fields_are_explicitly_diagnosed():
    src = _source()
    assert "[AI解释层匹配诊断]" in src
    assert "[AI解释层字段诊断]" in src
    assert "missing_fields = [key for key in required" in src
    assert "Core {ok_core} 六段 / Observation {ok_obs} 极简" in src


if __name__ == "__main__":
    tests = [
        test_ai_matcher_and_field_normalizer_are_wired,
        test_json_structure_failures_are_logged_without_raw_model_output,
        test_missing_tickers_and_fields_are_explicitly_diagnosed,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Result: {len(tests)}/{len(tests)} passed")
