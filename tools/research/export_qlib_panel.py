#!/usr/bin/env python3
"""Export a PIT snapshot into per-instrument CSV files for Qlib-compatible use.

Qlib's native store is binary; this exporter deliberately produces a neutral
per-instrument CSV layout so a Qlib handler can be written without depending on
a network download.  It does not install, import, or require Qlib.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


RESERVED = {"Scan_Date", "Technical_Date", "Ticker", "Date", "schema_version"}


def export_panel(snapshot: str | Path, outdir: str | Path) -> dict:
    src = Path(snapshot)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(src, low_memory=False)
    required = {"Technical_Date", "Ticker", "Price"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing columns: {missing}")
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Technical_Date"], errors="coerce")
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    df = df.dropna(subset=["Date", "Ticker"])
    feature_cols = [c for c in df.columns if c not in RESERVED]
    manifest = {
        "source": str(src),
        "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "feature_columns": feature_cols,
        "instruments": {},
    }
    for ticker, group in df.groupby("Ticker", sort=True):
        group = group.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
        target = out / f"{ticker}.csv"
        group[["Date", *feature_cols]].to_csv(target, index=False, encoding="utf-8")
        manifest["instruments"][ticker] = {
            "rows": int(len(group)),
            "date_min": str(group["Date"].min().date()),
            "date_max": str(group["Date"].max().date()),
            "file": target.name,
        }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--outdir", required=True)
    args = p.parse_args(argv)
    manifest = export_panel(args.snapshot, args.outdir)
    print(f"exported instruments={len(manifest['instruments'])} features={len(manifest['feature_columns'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
