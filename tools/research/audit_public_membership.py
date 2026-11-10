#!/usr/bin/env python3
"""Audit public historical S&P 500 membership datasets against the current panel.

Membership is not OHLCV.  This script only reports membership/ticker coverage;
it never fills prices or writes production data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml


def load_coiltrade(path: Path) -> tuple[set[str], set[str], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    current = {str(x).upper() for x in data.get("current", [])}
    changes = data.get("changes", [])
    all_tickers = set(current)
    dates = []
    for row in changes:
        for key in ("added", "removed"):
            value = str(row.get(key) or "").upper().strip()
            if value:
                all_tickers.add(value)
        if row.get("date"):
            dates.append(str(row["date"]))
    return current, all_tickers, dates


def load_shardul(directory: Path) -> tuple[set[str], list[str]]:
    all_tickers = set()
    dates = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        all_tickers.update(str(x).upper() for x in data.get("tickers_on_Jan_1", []))
        dates.append(str(data.get("year", "")))
    return all_tickers, dates


def audit(coil_path: Path, shard_dir: Path, price_panel: Path, failed_csv: Path) -> dict:
    coil_current, coil_all, coil_dates = load_coiltrade(coil_path)
    shard_all, shard_years = load_shardul(shard_dir)
    price = set(pd.read_csv(price_panel, usecols=["Ticker"])["Ticker"].astype(str).str.upper())
    failed = set(pd.read_csv(failed_csv, dtype=str, keep_default_na=False)["ticker"].str.upper())
    return {
        "research_only": True,
        "coiltrade": {
            "current": len(coil_current),
            "all_membership_tickers": len(coil_all),
            "change_rows": len(coil_dates),
            "date_min": min(coil_dates) if coil_dates else None,
            "date_max": max(coil_dates) if coil_dates else None,
            "failed_overlap": len(failed & coil_all),
            "failed_missing": sorted(failed - coil_all),
            "price_panel_overlap": len(price & coil_all),
            "membership_not_in_price_panel": len(coil_all - price),
        },
        "shardul": {
            "all_membership_tickers": len(shard_all),
            "years": len([x for x in shard_years if x]),
            "date_min": min([x for x in shard_years if x]) if shard_years else None,
            "date_max": max([x for x in shard_years if x]) if shard_years else None,
            "failed_overlap": len(failed & shard_all),
            "failed_missing": sorted(failed - shard_all),
            "price_panel_overlap": len(price & shard_all),
            "membership_not_in_price_panel": len(shard_all - price),
        },
        "price_panel_tickers": len(price),
        "failed_tickers": len(failed),
        "limitations": [
            "membership data does not contain OHLCV",
            "community/derived membership data requires independent date validation",
            "overlap counts do not prove price availability for delisted names",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coiltrade", required=True)
    p.add_argument("--shardul-dir", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--failed-csv", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    out = audit(Path(args.coiltrade), Path(args.shardul_dir), Path(args.price_panel), Path(args.failed_csv))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
