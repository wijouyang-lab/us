"""Deterministic AI explanation coverage diagnostics for Dashboard exports."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


CORE_FIELDS = (
    "industry_logic", "news_cn", "premarket_conclusion",
    "catalysts", "risks", "invalidation",
)
OBSERVATION_FIELDS = ("industry_logic", "catalysts", "risks")


def summarize_ai_coverage(stocks: Sequence[Mapping]) -> dict:
    """Summarize event-level AI coverage without generating or backfilling text.

    Core events require all six explanation fields. Observation events require
    only industry logic, catalysts, and risks. Ticker-only historical fallback is
    deliberately not attempted because explanation belongs to a specific event.
    """
    any_text_count = 0
    complete_count = 0
    missing_details = []
    for stock in stocks:
        ticker = str(stock.get("ticker") or "?").strip().upper()
        bucket = str(stock.get("bucket") or "").strip()
        required = CORE_FIELDS if bucket == "Core" or stock.get("recommendation_tag") == "Core_Dragon" else OBSERVATION_FIELDS
        ai = stock.get("ai") or {}
        filled = {
            field: bool(str(ai.get(field) or "").strip())
            for field in required
        }
        if any(filled.values()):
            any_text_count += 1
        missing = [field for field in required if not filled[field]]
        if not missing:
            complete_count += 1
        else:
            missing_details.append({
                "ticker": ticker,
                "recommendation_id": str(stock.get("recommendation_id") or "").strip(),
                "missing_fields": missing,
            })

    total = len(stocks)
    if total and complete_count == total:
        status = "complete"
    elif any_text_count:
        status = "partial"
    else:
        status = "pending"
    return {
        "status": status,
        "total": total,
        "any_text": any_text_count,
        "complete": complete_count,
        "missing": missing_details,
    }
