from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.ai_coverage import summarize_ai_coverage


def test_core_requires_six_fields_but_observation_requires_three():
    result = summarize_ai_coverage([
        {
            "ticker": "AAPL", "bucket": "Core",
            "ai": {
                "industry_logic": "逻辑", "news_cn": "新闻",
                "premarket_conclusion": "时段", "catalysts": "催化",
                "risks": "风险", "invalidation": "失效",
            },
        },
        {
            "ticker": "MSFT", "bucket": "Observation",
            "ai": {"industry_logic": "逻辑", "catalysts": "催化", "risks": "风险"},
        },
    ])
    assert result["status"] == "complete"
    assert result["any_text"] == 2
    assert result["complete"] == 2
    assert result["missing"] == []


def test_partial_event_reports_missing_fields_and_event_identity():
    result = summarize_ai_coverage([
        {
            "ticker": "XLE", "bucket": "Core",
            "recommendation_id": "XLE|2026-06-04|Core_Dragon",
            "ai": {"industry_logic": "历史文本"},
        },
    ])
    assert result["status"] == "partial"
    assert result["any_text"] == 1
    assert result["complete"] == 0
    assert result["missing"] == [{
        "ticker": "XLE",
        "recommendation_id": "XLE|2026-06-04|Core_Dragon",
        "missing_fields": ["news_cn", "premarket_conclusion", "catalysts", "risks", "invalidation"],
    }]


def test_no_ai_text_is_pending_not_fabricated():
    result = summarize_ai_coverage([
        {"ticker": "XOM", "bucket": "Core", "ai": {}},
        {"ticker": "WM", "bucket": "Observation", "ai": {}},
    ])
    assert result["status"] == "pending"
    assert result["any_text"] == 0
    assert result["complete"] == 0
    assert [x["ticker"] for x in result["missing"]] == ["XOM", "WM"]


if __name__ == "__main__":
    tests = [
        test_core_requires_six_fields_but_observation_requires_three,
        test_partial_event_reports_missing_fields_and_event_identity,
        test_no_ai_text_is_pending_not_fabricated,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Result: {len(tests)}/{len(tests)} passed")
