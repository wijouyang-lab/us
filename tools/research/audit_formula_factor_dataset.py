"""Read-only structural audit for the tracked formula-factor research dataset."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def audit_dataset(input_path: str) -> dict:
    frame = pd.read_csv(input_path)
    date_col = next((c for c in ("Snapshot_Date", "Technical_Date", "Scan_Date") if c in frame), None)
    if date_col is None or "Ticker" not in frame:
        raise ValueError("dataset must contain a supported date column and Ticker")
    dates = pd.to_datetime(frame[date_col], errors="coerce").dt.normalize()
    forward_cols = [c for c in frame if c.upper().startswith("FORWARD_RETURN_")]
    if not forward_cols:
        raise ValueError("dataset has no Forward_Return_* labels")
    key = pd.DataFrame({"date": dates, "ticker": frame["Ticker"].astype(str)})
    valid_key = key.dropna(subset=["date", "ticker"])
    duplicate_rows = int(valid_key.duplicated(["date", "ticker"], keep=False).sum())
    daily = pd.DataFrame({"date": dates, "ticker": frame["Ticker"].astype(str)}).dropna(subset=["date"])
    coverage = daily.groupby("date")["ticker"].nunique()
    numeric_features = []
    for col in frame.columns:
        if col in {"Ticker", "Scan_Date", "Technical_Date", "Snapshot_Date", "schema_version"}:
            continue
        if col.upper().startswith(("FORWARD_RETURN_", "WIN_")) or col.upper() in {"TARGET", "LABEL", "OUTCOME"}:
            continue
        values = pd.to_numeric(frame[col], errors="coerce")
        if values.notna().sum() and values.nunique(dropna=True) > 1:
            numeric_features.append(col)
    missingness = {}
    for col in numeric_features + forward_cols:
        values = pd.to_numeric(frame[col], errors="coerce")
        missingness[col] = round(float(values.isna().mean()), 6)
    label_stats = {}
    for col in forward_cols:
        values = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        label_stats[col] = {
            "n": int(values.size),
            "mean": round(float(values.mean()), 8) if len(values) else None,
            "median": round(float(values.median()), 8) if len(values) else None,
            "min": round(float(values.min()), 8) if len(values) else None,
            "max": round(float(values.max()), 8) if len(values) else None,
            "outside_abs_100pct": int((values.abs() > 1.0).sum()),
        }
    return {
        "input": str(input_path),
        "row_count": int(len(frame)),
        "date_column_used": date_col,
        "invalid_date_rows": int(dates.isna().sum()),
        "date_min": str(dates.min().date()) if dates.notna().any() else None,
        "date_max": str(dates.max().date()) if dates.notna().any() else None,
        "unique_dates": int(dates.nunique()),
        "unique_tickers": int(frame["Ticker"].nunique(dropna=True)),
        "duplicate_date_ticker_rows": duplicate_rows,
        "daily_ticker_coverage": {
            "min": int(coverage.min()) if len(coverage) else 0,
            "median": float(coverage.median()) if len(coverage) else 0,
            "max": int(coverage.max()) if len(coverage) else 0,
        },
        "numeric_feature_count_excluding_labels": len(numeric_features),
        "numeric_features": numeric_features,
        "forward_return_columns": forward_cols,
        "missing_fraction_by_feature_or_label": missingness,
        "forward_return_summary": label_stats,
        "warnings": [
            msg for condition, msg in [
                (duplicate_rows > 0, "Duplicate date/ticker rows exist; investigate before interpreting cross-sectional ranks."),
                (dates.isna().any(), "Rows with unparseable dates exist."),
                (any(v["outside_abs_100pct"] for v in label_stats.values()), "Some forward-return labels exceed +/-100%; verify corporate actions and label construction."),
                (coverage.nunique() > 1, "Cross-sectional ticker coverage varies over time; confirm point-in-time universe membership."),
            ] if condition
        ],
        "limitations": [
            "This is a structural/data-distribution audit only; it cannot prove historical universe membership or point-in-time feature availability.",
            "No rows are modified, imputed, or silently removed from the source dataset.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit_dataset(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"rows={result['row_count']} dates={result['unique_dates']} tickers={result['unique_tickers']}")
    print(f"duplicate_date_ticker_rows={result['duplicate_date_ticker_rows']}; warnings={len(result['warnings'])}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
