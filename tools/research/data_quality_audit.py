#!/usr/bin/env python3
"""Phase 2.1 data-quality audit for the local US price panel.

Research only. Does not fetch data or modify production files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def summarize_price_panel(df: pd.DataFrame) -> dict:
    d = df.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d["Ticker"] = d["Ticker"].astype(str).str.upper().str.strip()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["Date", "Ticker"])
    d = d.sort_values(["Ticker", "Date"])
    ret = d.groupby("Ticker")["Close"].pct_change()
    invalid = (
        (d["High"] < d["Low"]) | (d["High"] < d["Open"]) | (d["High"] < d["Close"])
        | (d["Low"] > d["Open"]) | (d["Low"] > d["Close"])
    )
    return {
        "rows": int(len(d)),
        "tickers": int(d["Ticker"].nunique()),
        "date_min": str(d["Date"].min().date()) if len(d) else None,
        "date_max": str(d["Date"].max().date()) if len(d) else None,
        "duplicate_ticker_date": int(d.duplicated(["Ticker", "Date"]).sum()),
        "null_close": int(d["Close"].isna().sum()),
        "nonpositive_close": int((d["Close"] <= 0).sum()),
        "zero_volume": int((d["Volume"] <= 0).sum()),
        "ohlc_invalid": int(invalid.sum()),
        "abs_daily_ret_gt_50pct": int((ret.abs() > 0.50).sum()),
        "abs_daily_ret_gt_90pct": int((ret.abs() > 0.90).sum()),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    df = pd.read_csv(args.price_panel, usecols=["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"])
    result = summarize_price_panel(df)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
