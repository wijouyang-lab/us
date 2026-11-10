#!/usr/bin/env python3
"""Classify PIT price-refresh failures with SEC identity evidence and aliases.

Reads the existing audit JSON, the SEC company_tickers.json, the repository
ticker-alias registry, and the current 10-year price panel. It never downloads
prices and never fills missing values.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def load_aliases(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {r["old_ticker"].upper(): r for r in df.to_dict("records")}


def load_sec(path: Path) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {v["ticker"].upper(): v for v in raw.values() if v.get("ticker")}


def classify(failures: list[dict], sec: dict, aliases: dict, price_tickers: set[str]) -> list[dict]:
    rows = []
    for item in failures:
        ticker = str(item["ticker"]).upper()
        alias = aliases.get(ticker)
        canonical = str(alias["canonical_ticker"]).upper() if alias else ""
        sec_present = ticker in sec
        if canonical and canonical in sec:
            category = "renamed_or_reorganized"
            action = f"ticker maps to current SEC ticker {canonical}; rebuild under that symbol"
        elif sec_present:
            category = "active_listing_price_source_failure"
            action = "SEC identity exists; retry a current/independent price provider"
        else:
            category = "delisted_acquired_or_unresolved_identity"
            action = "no current SEC ticker match; verify merger/delisting filing; free OHLCV unverified"
        rows.append({
            "ticker": ticker,
            "category": category,
            "canonical_ticker": canonical,
            "sec_current_ticker_present": sec_present,
            "in_current_10y_panel": ticker in price_tickers,
            "recovery_method_attempted": item.get("recovery_method", ""),
            "audit_status": item.get("status", ""),
            "evidence": item.get("fallback_error", "")[:500],
            "available_identity_source": "SEC company_tickers.json" if sec_present or canonical else "SEC/company filing may still identify issuer",
            "recoverable_fields": "identity only" if not (sec_present or canonical) else "identity; OHLCV only if an independent price source verifies it",
            "action": action,
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit-json", required=True)
    p.add_argument("--sec-json", required=True)
    p.add_argument("--aliases", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    audit = json.loads(Path(args.audit_json).read_text(encoding="utf-8"))
    sec = load_sec(Path(args.sec_json))
    aliases = load_aliases(Path(args.aliases))
    price = pd.read_csv(args.price_panel, usecols=["Ticker"])
    price_tickers = set(price["Ticker"].astype(str).str.upper().unique())
    rows = classify(audit["download_failures"], sec, aliases, price_tickers)
    out = pd.DataFrame(rows)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8")
    print(out["category"].value_counts().to_string())
    print(f"wrote {len(out)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
