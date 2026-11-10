#!/usr/bin/env python3
"""Fail-closed identity/quality gate for delisted securities.

Identity, price quality, terms, and independent cross-check are separate gates.
A data series cannot be imported unless all pass.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd


def validate_identity(record: dict[str, Any]) -> list[str]:
    errs = []
    for key in ("ticker", "cik", "company", "ticker_valid_to", "last_trade_date"):
        if not record.get(key):
            errs.append(f"missing_{key}")
    if record.get("ticker_valid_from") and record.get("last_trade_date"):
        if record["last_trade_date"] < record["ticker_valid_from"]:
            errs.append("last_trade_before_ticker_start")
    if record.get("ticker_valid_to") and record.get("last_trade_date"):
        if record["last_trade_date"] > record["ticker_valid_to"]:
            errs.append("last_trade_after_ticker_end")
    if record.get("event_date") and record.get("last_trade_date"):
        if record["event_date"] < record["last_trade_date"]:
            errs.append("event_before_last_trade")
    return errs


def validate_series(frame: pd.DataFrame, record: dict[str, Any],
                    tolerance_days: int = 5) -> list[str]:
    errs = []
    if frame is None or frame.empty:
        return ["empty_series"]
    f = frame.copy()
    if not isinstance(f.index, pd.DatetimeIndex):
        if "Date" not in f.columns:
            return ["missing_date"]
        f["Date"] = pd.to_datetime(f["Date"], errors="coerce")
        f = f.dropna(subset=["Date"]).set_index("Date")
    f = f.sort_index()
    if f.index.duplicated().any():
        errs.append("duplicate_dates")
    if (f.index.weekday >= 5).any():
        errs.append("weekend_rows")
    for col in ("Open", "High", "Low", "Close"):
        if col not in f.columns:
            errs.append(f"missing_{col.lower()}")
    if errs:
        return errs
    x = f[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce")
    if x.isna().any().any():
        errs.append("missing_ohlc")
    if (x <= 0).any().any():
        errs.append("nonpositive_price")
    if not ((f["High"] >= f[["Open", "Close", "Low"]].max(axis=1)).all()
            and (f["Low"] <= f[["Open", "Close", "High"]].min(axis=1)).all()):
        errs.append("invalid_ohlc")
    last = f.index.max().date()
    end = date.fromisoformat(record["ticker_valid_to"])
    if last > end + timedelta(days=tolerance_days):
        errs.append("series_extends_after_ticker_end")
    if f.index.min().date() > end:
        errs.append("series_starts_after_ticker_end")
    return errs


def evaluate(record: dict[str, Any], frame: pd.DataFrame, *,
             terms_status: str, independent_source: bool,
             canonical_write: bool = False) -> dict[str, Any]:
    errs = validate_identity(record) + validate_series(frame, record)
    if terms_status != "approved":
        errs.append("terms_unresolved")
    if not independent_source:
        errs.append("no_independent_crosscheck")
    if canonical_write:
        errs.append("canonical_write_not_allowed")
    return {"approved": not errs, "errors": errs}
