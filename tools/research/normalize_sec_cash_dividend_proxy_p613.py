"""Normalize SEC cash-dividend facts into CASH_DIVIDENDS_PAID / proxy fields."""
from __future__ import annotations
from datetime import date

CASH_TAGS = {"DividendsPaid", "PaymentsOfDividends", "PaymentsOfDividendsCommonStock",
             "PaymentsOfDividendsPreferredStockAndPreferenceStock",
             "DividendsCommonStockCash", "DividendsCash", "Dividends",
             "DividendsCommonStock", "PaymentsOfOrdinaryDividends"}
PER_SHARE_TAGS = {"CommonStockDividendsPerShareDeclared",
                  "CommonStockDividendsPerShareCashPaid",
                  "CommonStockDividendsPerShareDeclared"}
CASH_METRIC = "DividendsPaid"


def parse_date(v):
    try: return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError): return None


def normalize_cash(raw_value, unit, tag):
    """Return (normalized_cash, status). Never turns per-share into total cash."""
    try: x = float(raw_value)
    except (TypeError, ValueError): return None, "VALUE_INVALID"
    if tag in PER_SHARE_TAGS or unit == "USD/shares":
        return None, "PER_SHARE_FACT_NOT_TOTAL_CASH"
    if tag not in CASH_TAGS:
        return None, "UNSUPPORTED_CASH_TAG"
    if unit not in ("USD", "CAD", "EUR", "GBP", "JPY", "BRL", "MXN", "AUD",
                    "CNY", "HKD", "INR", "KRW", "ZAR", "SEK", "DKK", "NOK",
                    "CHF", "TWD", "SGD", "PEN", "COP", "CLP", "ARS", "TRY"):
        return None, "UNSUPPORTED_UNIT"
    # Cash-flow facts may be negative under a sign convention; magnitude is the
    # cash dividend, while raw_value keeps the original sign.
    return abs(x), "CASH_FACT_NORMALIZED"


def period_type(start, end, filed):
    s, e, f = parse_date(start), parse_date(end), parse_date(filed)
    if not e or not f: return "UNKNOWN"
    if not s: return "INSTANT"
    days = (e - s).days
    if 80 <= days <= 110: return "QUARTER"
    if 160 <= days <= 290: return "YTD"
    if 300 <= days <= 400: return "ANNUAL"
    return "OTHER"


def ttm_status(periods):
    """periods: list[(start,end)]; requires four non-overlapping quarters."""
    try:
        ps = sorted((parse_date(a), parse_date(b)) for a, b in periods)
    except Exception:
        return "TTM_UNAVAILABLE"
    if len(ps) < 4: return "TTM_UNAVAILABLE"
    # take four latest, validate contiguous non-overlap and ~quarter durations
    last = ps[-4:]
    for (s1, e1), (s2, e2) in zip(last, last[1:]):
        if not s1 or not e1 or not s2 or not e2: return "TTM_UNAVAILABLE"
        if not (80 <= (e1-s1).days <= 110): return "TTM_UNAVAILABLE"
        if (s2 - e1).days != 1: return "TTM_UNAVAILABLE"
    return "TTM_AVAILABLE"
