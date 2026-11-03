"""Calibrated IBKR Pro Tiered US stock/ETF cost model.

This is a research simulation. Venue/pass-through fees cannot be reconstructed
from historical SmartRouting fills; they are disclosed as an assumption band.
"""
from __future__ import annotations

import datetime as dt

COMMISSION_MIN = 0.35
COMMISSION_PER_SHARE = 0.0035
COMMISSION_MAX_PCT = 0.01
SEC_RATE = 0.0000206          # sell notional
TAF_PER_SHARE = 0.000166      # historical/current pre-holiday
TAF_MAX = 8.30
CAT_PER_SHARE = 0.000003
CLEARING_PER_SHARE = 0.00020
CLEARING_MAX_PCT = 0.005      # assumption: notional cap
EXCHANGE_BASE_PER_SHARE = 0.00010   # assumption midpoint of 0..0.0003
EXCHANGE_RANGE = (0.0, 0.00030)
TAF_HOLIDAY = (dt.date(2026, 10, 1), dt.date(2026, 12, 31))


def fees(shares, price, side, date=None, exchange_per_share=None,
         layer="historical_backtest"):
    if layer not in ("historical_backtest", "forward_estimate"):
        raise ValueError("unknown cost layer")
    shares = abs(float(shares)); notional = shares * float(price)
    commission = max(COMMISSION_MIN, min(COMMISSION_PER_SHARE * shares,
                                          COMMISSION_MAX_PCT * notional))
    sec = SEC_RATE * notional if side == "SELL" else 0.0
    taf = 0.0
    if side == "SELL":
        d = date.date() if hasattr(date, "date") else date
        if isinstance(d, str):
            d = dt.date.fromisoformat(d[:10])
        holiday = d is not None and TAF_HOLIDAY[0] <= d <= TAF_HOLIDAY[1]
        if not holiday:
            taf = min(TAF_PER_SHARE * shares, TAF_MAX)
    cat = CAT_PER_SHARE * shares
    clearing = min(CLEARING_PER_SHARE * shares, CLEARING_MAX_PCT * notional)
    ex = (EXCHANGE_BASE_PER_SHARE if exchange_per_share is None else exchange_per_share) * shares
    total = commission + sec + taf + cat + clearing + ex
    return {"commission": commission, "sec_fee": sec, "taf_fee": taf,
            "cat_fee": cat, "clearing_fee": clearing, "exchange_fee": ex,
            "model_layer": layer, "cost": total}


def range_fees(shares, price, side, date=None):
    lo = fees(shares, price, side, date, EXCHANGE_RANGE[0])
    hi = fees(shares, price, side, date, EXCHANGE_RANGE[1])
    return lo, hi
