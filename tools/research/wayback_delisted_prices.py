"""Free Internet Archive fallback for legacy Yahoo Finance delisted-ticker CSVs.

This is best-effort research-only recovery. Wayback snapshots may be partial or
stale, so callers must run the existing OHLC validation and PIT coverage gates.
No API token or paid data service is required.
"""
from __future__ import annotations

from datetime import date
from io import StringIO
from urllib.parse import quote, urlparse

import pandas as pd

CDX_URL = "https://web.archive.org/cdx/search/cdx"
ALLOWED_ARCHIVE_HOSTS = {
    "real-chart.finance.yahoo.com",
    "ichart.finance.yahoo.com",
    "chart.finance.yahoo.com",
}


def fetch_wayback_yahoo_csv_history(session, symbol: str, start: date, end_exclusive: date) -> pd.DataFrame:
    """Fetch one archived legacy Yahoo CSV, if the Wayback CDX index has it.

    Only known Yahoo legacy chart hosts are accepted from CDX results. This source
    is intentionally attempted after live Yahoo paths and before optional paid data.
    """
    ticker = str(symbol).strip().upper().replace(".", "-")
    if not ticker or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-^=" for ch in ticker):
        raise RuntimeError("unsupported ticker format for Wayback lookup")

    params = {
        "url": f"real-chart.finance.yahoo.com/table.csv?s={ticker}",
        "output": "json",
        "fl": "timestamp,original,statuscode,length,mimetype",
        "filter": "statuscode:200",
        "collapse": "digest",
        "from": "1996",
        "to": "2017",
    }
    try:
        response = session.get(CDX_URL, params=params, timeout=20)
        response.raise_for_status()
        rows = response.json()
    except Exception as exc:
        raise RuntimeError(f"Wayback CDX lookup failed ({type(exc).__name__})") from None

    if not isinstance(rows, list) or len(rows) < 2:
        raise RuntimeError("Wayback has no indexed legacy Yahoo CSV for ticker")

    header = rows[0]
    try:
        timestamp_idx = header.index("timestamp")
        original_idx = header.index("original")
        status_idx = header.index("statuscode")
        length_idx = header.index("length")
    except (ValueError, AttributeError):
        raise RuntimeError("Wayback CDX response has an unexpected schema") from None

    candidates = []
    for row in rows[1:]:
        if not isinstance(row, list) or len(row) <= max(timestamp_idx, original_idx, status_idx, length_idx):
            continue
        original = str(row[original_idx])
        parsed = urlparse(original)
        if parsed.hostname not in ALLOWED_ARCHIVE_HOSTS or row[status_idx] != "200":
            continue
        if not parsed.path.endswith("/table.csv"):
            continue
        try:
            size = int(row[length_idx] or 0)
        except (TypeError, ValueError):
            size = 0
        candidates.append((size, str(row[timestamp_idx]), original))

    if not candidates:
        raise RuntimeError("Wayback has no usable legacy Yahoo CSV snapshot")

    # Prefer the largest archived file, which is more likely to cover the full listing.
    candidates.sort(reverse=True)
    last_error = "no usable archived CSV"
    for _, timestamp, original in candidates[:3]:
        archived_url = f"https://web.archive.org/web/{quote(timestamp, safe='')}id_/{original}"
        try:
            archived = session.get(archived_url, timeout=30)
            archived.raise_for_status()
            frame = pd.read_csv(StringIO(archived.text))
        except Exception as exc:
            last_error = f"archived CSV fetch/parse failed ({type(exc).__name__})"
            continue

        normalised = {str(column).strip().lower().replace("_", " "): column for column in frame.columns}
        required = {"date", "open", "high", "low", "close"}
        if not required.issubset(normalised):
            last_error = "archived response is not a legacy Yahoo OHLC CSV"
            continue
        adj_column = normalised.get("adj close")
        if adj_column is None:
            last_error = "archived CSV has no adjusted-close column"
            continue

        frame = frame.rename(columns={
            normalised["open"]: "Open",
            normalised["high"]: "High",
            normalised["low"]: "Low",
            normalised["close"]: "Close",
            adj_column: "Adj Close",
            **({normalised["volume"]: "Volume"} if "volume" in normalised else {}),
        })
        frame["Date"] = pd.to_datetime(frame[normalised["date"]], errors="coerce")
        frame = frame.dropna(subset=["Date"]).set_index("Date").sort_index()
        frame = frame.loc[(frame.index.date >= start) & (frame.index.date < end_exclusive)]
        if frame.empty or frame["Close"].notna().sum() == 0:
            last_error = "archived CSV has no rows in requested date window"
            continue
        if "Volume" not in frame.columns:
            frame["Volume"] = pd.NA
        return frame[["Open", "High", "Low", "Close", "Adj Close", "Volume"]]

    raise RuntimeError(f"Wayback has no valid history for {ticker}: {last_error}")
