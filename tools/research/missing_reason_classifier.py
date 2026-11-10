#!/usr/bin/env python3
"""Classify missing historical members without inferring delisting from a gap."""
from __future__ import annotations

from typing import Any

DELISTED = "DELISTED_OR_ACQUIRED"
CHANGED = "TICKER_OR_NAME_CHANGED"
REUSE = "TICKER_REUSE_SUSPECTED"
STILL = "STILL_TRADING"
UNRESOLVED = "IDENTITY_UNRESOLVED"
HISTORY_ONLY = "HISTORICAL_MEMBERSHIP_ONLY"
COVERAGE = "DATA_COVERAGE_GAP"


def classify(security: dict[str, Any]) -> dict[str, Any]:
    tickers = [str(x).upper() for x in (security.get("tickers") or [])]
    old = str(security.get("ticker", "")).upper()
    forms = security.get("delisting_forms") or []
    if not security.get("cik") or not security.get("sec_name"):
        category = UNRESOLVED
    elif tickers and old in tickers:
        category = STILL
    elif tickers and old not in tickers:
        category = CHANGED
    elif forms:
        category = DELISTED
    else:
        category = UNRESOLVED
    if security.get("reuse_suspected") and category in (DELISTED, CHANGED):
        category = REUSE
    return {
        "category": category,
        "identity_status": "CIK_CONFIRMED" if security.get("cik") else "UNVERIFIED",
        "lifecycle_status": {
            STILL: "LISTED_UNDER_ORIGINAL_TICKER",
            CHANGED: "LISTED_UNDER_DIFFERENT_TICKER",
            DELISTED: "DELISTING_FORM_OBSERVED",
            REUSE: "ORIGINAL_TICKER_ENDED",
        }.get(category, "UNVERIFIED"),
        "price_status": "NO_SERIES_IN_CURRENT_PANEL",
        "recovery_status": {
            STILL: "PUBLIC_SOURCE_NOT_VALIDATED",
            CHANGED: "CURRENT_TICKER_NOT_MAPPED",
            DELISTED: "NO_APPROVED_FREE_SOURCE",
            REUSE: "TICKER_REUSE_HIGH_RISK",
        }.get(category, "IDENTITY_UNVERIFIED"),
    }
