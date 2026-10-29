#!/usr/bin/env python3
"""Validate a recovered delisted-series sample before it may enter research.

This does not fetch data. It rejects ticker reuse and post-delisting rows.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd


def validate_delisted_frame(frame: pd.DataFrame, removal_date: date,
                            *, tolerance_days: int = 30) -> dict[str, Any]:
    reasons = []
    if frame is None or frame.empty:
        return {"accepted": False, "reasons": ["empty_frame"]}
    f = frame.copy()
    if not isinstance(f.index, pd.DatetimeIndex):
        if "Date" not in f.columns:
            return {"accepted": False, "reasons": ["missing_date"]}
        f["Date"] = pd.to_datetime(f["Date"], errors="coerce")
        f = f.dropna(subset=["Date"]).set_index("Date")
    f = f.sort_index()
    first, last = f.index.min().date(), f.index.max().date()
    if first > removal_date:
        reasons.append("series_starts_after_delisting_ticker_reuse")
    if last < removal_date - timedelta(days=tolerance_days):
        reasons.append("series_ends_too_early")
    if last > removal_date + timedelta(days=tolerance_days):
        reasons.append("series_extends_after_delisting_ticker_reuse")
    for col in ("Open", "High", "Low", "Close"):
        if col not in f.columns:
            reasons.append(f"missing_{col.lower()}")
    if not reasons:
        x = f[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce")
        if x.isna().any().any() or (x <= 0).any().any():
            reasons.append("invalid_ohlc")
        elif not ((f["High"] >= f[["Open", "Close", "Low"]].max(axis=1)).all()
                  and (f["Low"] <= f[["Open", "Close", "High"]].min(axis=1)).all()):
            reasons.append("invalid_ohlc")
    return {"accepted": not reasons, "reasons": reasons,
            "first": first.isoformat(), "last": last.isoformat(), "rows": len(f)}
