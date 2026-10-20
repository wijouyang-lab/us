"""Strict matching of model-generated explanation rows to requested stock tickers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


_TICKER_KEYS = ("ticker", "symbol", "stock_ticker", "stock_symbol", "code")


def _normalize_ticker(value) -> str:
    text = str(value or "").strip().upper()
    # Common model formatting, e.g. "$AAPL" or "NASDAQ: AAPL".
    if ":" in text:
        text = text.rsplit(":", 1)[-1].strip()
    if text.startswith("$"):
        text = text[1:].strip()
    return text


def match_ai_rows(expected_items: Sequence[Mapping], rows: Sequence[Mapping]) -> tuple[dict[str, Mapping], list[str]]:
    """Match response rows only to requested tickers; return (matches, diagnostics).

    A positional fallback is allowed only when exactly one stock was requested and
    exactly one response object was returned without any ticker identifier. For
    multi-stock responses, missing/unknown identifiers are never guessed.
    """
    expected = {
        _normalize_ticker(item.get("Ticker")): item
        for item in expected_items
        if _normalize_ticker(item.get("Ticker"))
    }
    matches: dict[str, Mapping] = {}
    diagnostics: list[str] = []
    unidentified: list[Mapping] = []

    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            diagnostics.append(f"row[{index}] is not an object")
            continue
        raw_ticker = next((row.get(key) for key in _TICKER_KEYS if _normalize_ticker(row.get(key))), None)
        ticker = _normalize_ticker(raw_ticker)
        if not ticker:
            unidentified.append(row)
            continue
        if ticker not in expected:
            diagnostics.append(f"unexpected ticker {ticker}")
            continue
        if ticker in matches:
            diagnostics.append(f"duplicate ticker {ticker}")
            continue
        matches[ticker] = row

    if not matches and len(expected) == 1 and len(rows) == 1 and len(unidentified) == 1:
        only_ticker = next(iter(expected))
        matches[only_ticker] = unidentified[0]
        diagnostics.append(f"single-row fallback used for {only_ticker}")

    missing = sorted(set(expected) - set(matches))
    if missing:
        diagnostics.append("missing tickers: " + ",".join(missing))
    return matches, diagnostics
