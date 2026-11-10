#!/usr/bin/env python3
"""Read-only audit for the low-frequency research panels.

Checks the 2-year PIT snapshot and the 10-year current-universe price panel
for schema, duplicates, missing values, date integrity, and ticker overlap.
It never writes the production files.

This script is deliberately dependency-light: pandas/numpy only.
Qlib/OpenBB availability is reported separately, not assumed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _as_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def audit_price_history(path: str | Path) -> dict:
    df = pd.read_csv(path, low_memory=False)
    required = {"Date", "Ticker", "Open", "High", "Low", "Close", "Volume"}
    missing_cols = sorted(required - set(df.columns))
    if missing_cols:
        return {"path": str(path), "status": "INVALID_COLUMNS", "missing_columns": missing_cols}
    df = df.copy()
    df["Date"] = _as_date(df["Date"])
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    for c in ("Open", "High", "Low", "Close", "Volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    closed = pd.to_numeric(df["Close"], errors="coerce")
    return {
        "path": str(path),
        "status": "OK",
        "rows": int(len(df)),
        "tickers": int(df["Ticker"].nunique()),
        "dates": int(df["Date"].nunique()),
        "date_min": str(df["Date"].min().date()) if df["Date"].notna().any() else None,
        "date_max": str(df["Date"].max().date()) if df["Date"].notna().any() else None,
        "duplicate_date_ticker": int(df.duplicated(subset=["Date", "Ticker"]).sum()),
        "invalid_dates": int(df["Date"].isna().sum()),
        "weekend_rows": int((df["Date"].dt.weekday >= 5).sum()),
        "nonpositive_close": int((closed <= 0).sum()),
        "missing_close": int(closed.isna().sum()),
        "missing_volume": int(df["Volume"].isna().sum()),
        "missing_open": int(pd.to_numeric(df["Open"], errors="coerce").isna().sum()),
        "schema_versions": sorted(df["schema_version"].astype(str).unique().tolist())
        if "schema_version" in df.columns else [],
        "survivorship_note": "current-universe panel; delisted constituents are not represented by this file alone",
    }


def audit_snapshot(path: str | Path) -> dict:
    df = pd.read_csv(path, low_memory=False)
    required = {"Scan_Date", "Technical_Date", "Ticker", "Price"}
    missing_cols = sorted(required - set(df.columns))
    if missing_cols:
        return {"path": str(path), "status": "INVALID_COLUMNS", "missing_columns": missing_cols}
    df = df.copy()
    df["Technical_Date"] = _as_date(df["Technical_Date"])
    df["Scan_Date"] = _as_date(df["Scan_Date"])
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    feature_cols = [c for c in df.columns if c not in {"Scan_Date", "Technical_Date", "Ticker", "Price", "schema_version"}]
    scan_before_technical = int((df["Scan_Date"] < df["Technical_Date"]).sum())
    return {
        "path": str(path),
        "status": "OK",
        "rows": int(len(df)),
        "tickers": int(df["Ticker"].nunique()),
        "technical_dates": int(df["Technical_Date"].nunique()),
        "scan_dates": int(df["Scan_Date"].nunique()),
        "date_min": str(df["Technical_Date"].min().date()) if df["Technical_Date"].notna().any() else None,
        "date_max": str(df["Technical_Date"].max().date()) if df["Technical_Date"].notna().any() else None,
        "duplicate_date_ticker": int(df.duplicated(subset=["Technical_Date", "Ticker"]).sum()),
        "invalid_dates": int(df["Technical_Date"].isna().sum()),
        "weekend_rows": int((df["Technical_Date"].dt.weekday >= 5).sum()),
        "nonpositive_price": int((df["Price"] <= 0).sum()),
        "missing_price": int(df["Price"].isna().sum()),
        "scan_before_technical": scan_before_technical,
        "feature_columns": feature_cols,
        "feature_missing_pct": {
            c: round(float(pd.to_numeric(df[c], errors="coerce").isna().mean()), 6)
            for c in feature_cols
        },
        "schema_versions": sorted(df["schema_version"].astype(str).unique().tolist())
        if "schema_version" in df.columns else [],
        "pit_note": "Snapshot rows are keyed by Scan_Date + Technical_Date + Ticker; future information must be checked at feature construction, not inferred from this file alone.",
    }


def cross_panel(name_a: str, a: dict, name_b: str, b: dict) -> dict:
    if a.get("status") != "OK" or b.get("status") != "OK":
        return {"status": "SKIPPED", "reason": "one panel failed audit"}
    return {
        "status": "OK",
        "tickers_a": a["tickers"],
        "tickers_b": b["tickers"],
        "rows_a": a["rows"],
        "rows_b": b["rows"],
        "note": "Ticker-set overlap must be computed from files; this summary is a readiness signal only.",
    }


def qlib_openbb_status() -> dict:
    import importlib.util

    return {
        "qlib_installed": importlib.util.find_spec("qlib") is not None,
        "openbb_installed": importlib.util.find_spec("openbb") is not None,
        "qlib_note": "Qlib is a research engine, not a data source; install/import availability is separate from data coverage.",
        "openbb_note": "OpenBB is a provider router. Free providers must still be checked for delisted history and entitlement limits.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--price-history", required=True)
    p.add_argument("--output", default="research_lowfreq_data_audit.json")
    args = p.parse_args(argv)

    snap = audit_snapshot(args.snapshot)
    price = audit_price_history(args.price_history)
    report = {
        "research_only": True,
        "snapshot": snap,
        "price_history": price,
        "cross_panel": cross_panel("snapshot", snap, "price_history", price),
        "tooling": qlib_openbb_status(),
    }
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if snap.get("status") == "OK" and price.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
