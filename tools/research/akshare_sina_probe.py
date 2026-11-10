#!/usr/bin/env python3
"""Probe AKShare's Sina US-history endpoint for three delisted/reused names.

No account, token, or paid service is used. The endpoint is a free public route,
but its data-use terms are not established; this script stores a validation
summary only, never the full series or the canonical panel.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import akshare as ak
import pandas as pd

from tools.research.delisted_recovery_validator import validate_delisted_frame

SINA_URL = "https://finance.sina.com.cn/staticdata/us/{ticker}"
CASES = {
    "ADCT": date(2007, 10, 26),
    "TWTR": date(2022, 10, 27),
    "SIVB": date(2023, 3, 10),
}


def probe(ticker: str, removal: date) -> dict:
    row = {"ticker": ticker, "function": "stock_us_daily",
           "akshare_version": ak.__version__,
           "upstream": SINA_URL.format(ticker=ticker),
           "auth_required": False, "status": None}
    try:
        df = ak.stock_us_daily(symbol=ticker)
        row["rows"] = int(len(df))
        if not len(df):
            row["status"] = "empty"
            return row
        d = df.rename(columns={"date": "Date", "open": "Open", "high": "High",
                               "low": "Low", "close": "Close", "volume": "Volume"})
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
        d = d.dropna(subset=["Date"]).set_index("Date").sort_index()
        v = validate_delisted_frame(d, removal)
        row.update({
            "first": str(d.index.min().date()),
            "last": str(d.index.max().date()),
            "last_close": float(d["Close"].iloc[-1]),
            "duplicate_dates": int(d.index.duplicated().sum()),
            "weekend_rows": int((d.index.weekday >= 5).sum()),
            "ohlc_bad_rows": int(((d["High"] < d[["Open", "Close", "Low"]].max(axis=1)) |
                                  (d["Low"] > d[["Open", "Close", "High"]].min(axis=1))).sum()),
            "validator": v,
            "status": "accepted" if v["accepted"] else "rejected",
        })
    except Exception as exc:
        row.update({"status": "exception", "error": f"{type(exc).__name__}: {exc}"})
    return row


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    rows = [probe(t, d) for t, d in CASES.items()]
    payload = {
        "as_of": "2026-10-29T09:00:00Z",
        "source": "AKShare stock_us_daily -> Sina staticdata",
        "terms": "terms_confirmation_required; no bulk storage or redistribution",
        "canonical_write": False,
        "results": rows,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"results": [{"ticker": r["ticker"], "status": r["status"],
                                   "rows": r.get("rows"), "first": r.get("first"),
                                   "last": r.get("last"), "reasons": r.get("validator", {}).get("reasons")}
                                  for r in rows]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
