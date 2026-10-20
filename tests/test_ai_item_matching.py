from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.ai_item_matching import match_ai_rows


def test_matches_case_insensitive_tickers():
    matched, diagnostics = match_ai_rows([{"Ticker": "AAPL"}, {"Ticker": "MSFT"}],
                                         [{"ticker": "aapl", "industry_logic": "x"},
                                          {"ticker": "MSFT", "industry_logic": "y"}])
    assert set(matched) == {"AAPL", "MSFT"}
    assert not [d for d in diagnostics if d.startswith("missing tickers")]


def test_accepts_common_symbol_alias_and_prefix():
    matched, _ = match_ai_rows([{"Ticker": "AAPL"}], [{"symbol": "NASDAQ: $aapl", "risks": "r"}])
    assert matched["AAPL"]["risks"] == "r"


def test_single_candidate_can_use_safe_positional_fallback():
    matched, diagnostics = match_ai_rows([{"Ticker": "NVDA"}], [{"industry_logic": "逻辑"}])
    assert matched["NVDA"]["industry_logic"] == "逻辑"
    assert "single-row fallback used for NVDA" in diagnostics


def test_multi_candidate_missing_tickers_are_never_guessed():
    matched, diagnostics = match_ai_rows([{"Ticker": "AAPL"}, {"Ticker": "MSFT"}],
                                         [{"industry_logic": "A"}, {"industry_logic": "B"}])
    assert matched == {}
    assert any("missing tickers: AAPL,MSFT" in d for d in diagnostics)


def test_unexpected_and_duplicate_tickers_are_reported():
    matched, diagnostics = match_ai_rows([{"Ticker": "AAPL"}],
                                         [{"ticker": "AAPL", "industry_logic": "first"},
                                          {"ticker": "AAPL", "industry_logic": "second"},
                                          {"ticker": "ZZZZ", "industry_logic": "wrong"}])
    assert matched["AAPL"]["industry_logic"] == "first"
    assert "duplicate ticker AAPL" in diagnostics
    assert "unexpected ticker ZZZZ" in diagnostics


if __name__ == "__main__":
    tests = [
        test_matches_case_insensitive_tickers,
        test_accepts_common_symbol_alias_and_prefix,
        test_single_candidate_can_use_safe_positional_fallback,
        test_multi_candidate_missing_tickers_are_never_guessed,
        test_unexpected_and_duplicate_tickers_are_reported,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Result: {len(tests)}/{len(tests)} passed")
