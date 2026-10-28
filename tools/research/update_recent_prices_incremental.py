#!/usr/bin/env python3
"""Incrementally append recent Yahoo daily bars to the research price panel.

Only dates after the panel's last date are appended. No interpolation, no
synthetic rows, no delisted-ticker backfill, no production writes.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

COLUMNS = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]


def _valid_rows(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"])
    d = d[(d[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    d = d[(d["High"] >= d[["Open", "Close", "Low"]].max(axis=1))]
    d = d[(d["Low"] <= d[["Open", "Close", "High"]].min(axis=1))]
    d = d[d["Volume"] >= 0]
    d["Date"] = pd.to_datetime(d["Date"]).dt.date
    return d.drop_duplicates(["Date", "Ticker"], keep="last")


def append_recent(existing: pd.DataFrame, downloaded: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    existing = existing.copy()
    existing["Date"] = pd.to_datetime(existing["Date"]).dt.date
    last = max(existing["Date"])
    fresh = _valid_rows(downloaded)
    fresh = fresh[fresh["Date"] > last]
    if fresh.empty:
        return existing, {"last_existing": last.isoformat(), "new_rows": 0, "new_dates": []}
    fresh = fresh[fresh["Ticker"].isin(set(existing["Ticker"].astype(str).str.upper()))]
    fresh["Ticker"] = fresh["Ticker"].astype(str).str.upper()
    fresh["schema_version"] = "phase2b.v1"
    for col in ("Open", "High", "Low", "Close"):
        fresh[col] = fresh[col].astype(float).round(6)
    fresh["Volume"] = fresh["Volume"].astype("int64")
    combined = pd.concat([existing, fresh[COLUMNS]], ignore_index=True)
    combined = combined.drop_duplicates(["Date", "Ticker"], keep="first")
    return combined, {
        "last_existing": last.isoformat(),
        "new_rows": len(fresh),
        "new_dates": sorted({d.isoformat() for d in fresh["Date"]}),
        "new_tickers": int(fresh["Ticker"].nunique()),
    }


def download_batch(tickers: list[str], start: date, end: date, batch_size: int = 40) -> pd.DataFrame:
    import yfinance as yf

    try:
        yf.set_tz_cache_location(tempfile.mkdtemp(prefix="yf-cache-"))
    except Exception:
        pass
    rows = []
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            data = yf.download(
                batch, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                progress=False, auto_adjust=False, group_by="ticker", threads=True,
            )
        except Exception as exc:
            print(f"[batch {i // batch_size}] failed: {type(exc).__name__}: {exc}")
            continue
        if data is None or data.empty:
            continue
        for ticker in batch:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.get_level_values(0):
                    continue
                sub = data[ticker]
            else:
                sub = data
            for day, row in sub.iterrows():
                if pd.isna(row.get("Close")):
                    continue
                rows.append({
                    "Date": pd.Timestamp(day).date(),
                    "Ticker": ticker,
                    "Open": row.get("Open"), "High": row.get("High"),
                    "Low": row.get("Low"), "Close": row.get("Close"),
                    "Volume": row.get("Volume"), "schema_version": "phase2b.v1",
                })
    return pd.DataFrame(rows, columns=COLUMNS)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--metadata", required=True)
    p.add_argument("--end-date", default=date.today().isoformat())
    p.add_argument("--batch-size", type=int, default=40)
    args = p.parse_args(argv)
    existing = pd.read_csv(args.input)
    tickers = sorted(existing["Ticker"].astype(str).str.upper().unique())
    last = max(pd.to_datetime(existing["Date"]).dt.date)
    target = date.fromisoformat(args.end_date)
    if target <= last:
        print(f"no update needed: last={last} target={target}")
        return 1
    downloaded = download_batch(tickers, last, target, args.batch_size)
    updated, report = append_recent(existing, downloaded)
    missing = sorted(set(tickers) - set(downloaded["Ticker"].astype(str).str.upper())) if not downloaded.empty else tickers
    if downloaded.empty:
        download_status = "download_empty"
    elif report["new_rows"] == 0:
        download_status = "no_new_sessions"
    elif missing:
        download_status = "partial"
    else:
        download_status = "ok"
    legacy_invalid = int(((existing[["Open", "High", "Low", "Close"]] <= 0).any(axis=1) | (existing.High < existing[["Open", "Close", "Low"]].max(axis=1)) | (existing.Low > existing[["Open", "Close", "High"]].min(axis=1))).sum())
    report.update({
        "source": "yahoo_chart_yfinance",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requested_start": last.isoformat(),
        "requested_end": target.isoformat(),
        "download_status": download_status,
        "tickers_requested": len(tickers),
        "tickers_with_rows": int(downloaded["Ticker"].nunique()) if not downloaded.empty else 0,
        "tickers_with_new_rows": int(report.get("new_tickers") or 0),
        "tickers_missing": len(missing),
        "missing_sample": missing[:20],
        "legacy_invalid_rows": legacy_invalid,
        "new_last": max(updated["Date"]).isoformat(),
        "output_rows": len(updated),
        "research_only": True,
        "production_modified": False,
        "price_basis": "raw OHLCV; no adjusted-close column added",
    })
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    updated[COLUMNS].sort_values(["Date", "Ticker"]).to_csv(args.output, index=False, encoding="utf-8")
    Path(args.metadata).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 2 if download_status == "download_empty" else 0


if __name__ == "__main__":
    raise SystemExit(main())
