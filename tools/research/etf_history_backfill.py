#!/usr/bin/env python3
"""Download reproducible research-only ETF OHLCV/action histories from Yahoo Finance.

No API token is required. Output is intended for GitHub Actions artifacts, not
production use. The source is a third-party provider and may revise history.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Existing Trend V1 ETFs plus short-Treasury defensive candidates.
TICKERS = ("SPY", "GLD", "IWM", "QQQ", "TLT", "BIL", "SGOV", "SHV")
REQUIRED = ("Open", "High", "Low", "Close", "Adj Close", "Volume")
ACTION_COLUMNS = ("Dividends", "Stock Splits")


def normalize_history(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ValueError(f"{ticker}: provider returned empty history")
    d = frame.copy()
    if isinstance(d.columns, pd.MultiIndex):
        raise ValueError(f"{ticker}: unexpected MultiIndex history columns")
    missing = [column for column in REQUIRED if column not in d.columns]
    if missing:
        raise ValueError(f"{ticker}: missing required columns {missing}")
    index = pd.to_datetime(d.index, errors="coerce")
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    d["Date"] = index.normalize()
    d = d.reset_index(drop=True)
    for column in REQUIRED + ACTION_COLUMNS:
        if column not in d:
            d[column] = 0.0
        d[column] = pd.to_numeric(d[column], errors="coerce")
    d["Ticker"] = str(ticker).strip().upper()
    d = d[["Date", "Ticker", *REQUIRED, *ACTION_COLUMNS]]
    d = d.dropna(subset=["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"])
    d = d[(d["Open"] > 0) & (d["High"] > 0) & (d["Low"] > 0)
          & (d["Close"] > 0) & (d["Adj Close"] > 0) & (d["Volume"] >= 0)]
    if d.duplicated(["Date", "Ticker"]).any():
        raise ValueError(f"{ticker}: duplicate Date/Ticker rows")
    d = d.sort_values("Date").reset_index(drop=True)
    if len(d) < 252:
        raise ValueError(f"{ticker}: only {len(d)} rows; fewer than 252 sessions")
    d["Dividend_Event"] = d["Dividends"].fillna(0).ne(0)
    d["Split_Event"] = d["Stock Splits"].fillna(0).ne(0)
    return d


def download_ticker(ticker: str, *, retries: int = 3, sleep_seconds: float = 2.0) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is required; install yfinance>=1,<2") from exc

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            history = yf.Ticker(ticker).history(
                period="max",
                interval="1d",
                auto_adjust=False,
                actions=True,
                repair=False,
                timeout=30,
            )
            return normalize_history(history, ticker)
        except Exception as exc:  # provider/network errors are retried, then fail closed
            last_error = exc
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"{ticker}: failed after {retries} attempts: {last_error}") from last_error


def build_manifest(frames: dict[str, pd.DataFrame], *, downloaded_at: str, yfinance_version: str) -> dict:
    items = {}
    for ticker, frame in frames.items():
        items[ticker] = {
            "rows": int(len(frame)),
            "first_date": frame["Date"].min().date().isoformat(),
            "last_date": frame["Date"].max().date().isoformat(),
            "dividend_event_rows": int(frame["Dividend_Event"].sum()),
            "dividend_sum_per_share_provider_units": float(frame["Dividends"].sum()),
            "split_event_rows": int(frame["Split_Event"].sum()),
            "missing_adj_close": int(frame["Adj Close"].isna().sum()),
            "min_close": float(frame["Close"].min()),
            "max_close": float(frame["Close"].max()),
        }
    return {
        "status": "RESEARCH_ONLY_PROVIDER_DOWNLOAD",
        "source": "Yahoo Finance via yfinance; no API token",
        "downloaded_at_utc": downloaded_at,
        "yfinance_version": yfinance_version,
        "requested_symbols": list(TICKERS),
        "symbols": items,
        "limitations": [
            "Third-party historical data may be revised or corrected by the provider.",
            "Only currently existing funds are included; closed/liquidated ETF histories are not reconstructed.",
            "Adj Close is provider-adjusted and should be separately audited before total-return use.",
            "Open/High/Low/Close remain provider price fields; no execution fill or spread is implied.",
            "This artifact is not a point-in-time investable ETF universe and is not production data.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)

    import yfinance as yf

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: dict[str, pd.DataFrame] = {}
    for ticker in TICKERS:
        print(f"[ETF history] downloading {ticker}", flush=True)
        frame = download_ticker(
            ticker, retries=max(1, args.retries),
            sleep_seconds=max(0.0, args.sleep_seconds),
        )
        frame.drop(columns=["Dividend_Event", "Split_Event"]).to_csv(
            output_dir / f"{ticker}.csv", index=False, encoding="utf-8"
        )
        frames[ticker] = frame
        print(
            f"[ETF history] {ticker}: {len(frame)} rows, "
            f"{frame.Date.min().date()}..{frame.Date.max().date()}, "
            f"dividend rows={int(frame.Dividend_Event.sum())}",
            flush=True,
        )

    manifest = build_manifest(
        frames,
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        yfinance_version=str(yf.__version__),
    )
    manifest_path = Path(args.manifest_out)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
