#!/usr/bin/env python3
"""Fetch SPY as a separate research market proxy with raw and adjusted closes."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

COLUMNS = ["Date", "Ticker", "Open", "High", "Low", "Close", "Adj_Close", "Volume", "source", "schema_version"]


def normalize(raw: pd.DataFrame, source: str, fetched_at: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for day, r in raw.iterrows():
        try:
            o, h, l, c = (float(r[x]) for x in ("Open", "High", "Low", "Close"))
        except (KeyError, TypeError, ValueError):
            continue
        if not (o > 0 and h > 0 and l > 0 and c > 0 and h >= max(o, c, l) and l <= min(o, c, h)):
            continue
        adj = r.get("Adj Close")
        rows.append({
            "Date": pd.Timestamp(day).date().isoformat(),
            "Ticker": "SPY", "Open": o, "High": h, "Low": l, "Close": c,
            "Adj_Close": float(adj) if pd.notna(adj) else None,
            "Volume": int(r.get("Volume") or 0),
            "source": source, "schema_version": "spy-proxy-v1",
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    df = df.drop_duplicates(["Date", "Ticker"], keep="last").sort_values("Date")
    report = {
        "rows": len(df),
        "tickers": 1,
        "date_min": df["Date"].min() if len(df) else None,
        "date_max": df["Date"].max() if len(df) else None,
        "duplicates": 0,
        "invalid_rows_removed": len(raw) - len(df) if len(raw) >= len(df) else None,
        "adjusted_close_available": bool(len(df) and df["Adj_Close"].notna().all()),
        "source": source,
        "fetched_at_utc": fetched_at,
        "price_basis": "raw OHLCV plus provider Adj Close; not total-return unless explicitly used",
    }
    return df, report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--metadata", required=True)
    p.add_argument("--start", default="2016-09-19")
    p.add_argument("--end", default=date.today().isoformat())
    args = p.parse_args(argv)
    import yfinance as yf
    try:
        yf.set_tz_cache_location(tempfile.mkdtemp(prefix="yf-spy-"))
    except Exception:
        pass
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    raw = yf.download("SPY", start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                      progress=False, auto_adjust=False, group_by="ticker", threads=False)
    if raw is None or raw.empty:
        raise SystemExit("SPY download returned no rows")
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw["SPY"]
    fetched = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    df, report = normalize(raw, "yahoo_chart_yfinance", fetched)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8")
    Path(args.metadata).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
