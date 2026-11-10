#!/usr/bin/env python3
"""Build a machine-readable price-recovery audit for the 98 failed tickers.

Identity/membership evidence is kept separate from price evidence. A ticker with
verified identity but zero price rows is `identity_only`, not recovered.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build(identity_csv: Path, price_panel: Path, failed_csv: Path) -> pd.DataFrame:
    identity = pd.read_csv(identity_csv, dtype=str, keep_default_na=False)
    failed = pd.read_csv(failed_csv, dtype=str, keep_default_na=False)
    price = pd.read_csv(price_panel, dtype=str, keep_default_na=False)
    price["Date"] = pd.to_datetime(price["Date"], errors="coerce")
    price["Ticker"] = price["Ticker"].astype(str).str.upper().str.strip()
    grouped = {t: g for t, g in price.groupby("Ticker")}
    rows = []
    for rec in failed.to_dict("records"):
        ticker = str(rec["ticker"]).upper()
        ident = identity[identity["ticker"].str.upper() == ticker]
        ident = ident.iloc[0].to_dict() if not ident.empty else {}
        g = grouped.get(ticker)
        rows_count = 0 if g is None else int(g["Date"].notna().sum())
        first = "" if g is None or g["Date"].dropna().empty else str(g["Date"].min().date())
        last = "" if g is None or g["Date"].dropna().empty else str(g["Date"].max().date())
        identity_ok = bool(ident.get("cik")) and ident.get("identity_confidence") in {"high", "medium"}
        membership_ok = bool(ident.get("membership_removed") or ident.get("membership_added"))
        if not identity_ok:
            status = "unresolved_identity"
        elif rows_count == 0:
            status = "no_usable_free_source_found" if not membership_ok else "identity_only"
        else:
            status = "recovered_but_unverified"
        rows.append({
            "ticker": ticker,
            "identity_verified": identity_ok,
            "membership_verified": membership_ok,
            "price_source": "existing_yahoo_panel" if rows_count else "",
            "valid_ohlcv_rows": rows_count,
            "first_valid_date": first,
            "last_valid_date": last,
            "adjusted_price_available": False,
            "corporate_actions_verified": False,
            "independent_crosscheck_available": False,
            "recovery_status": status,
            "evidence_url": ident.get("identity_evidence_url", ""),
            "failure_reason": rec.get("evidence", "")[:300],
            "identity_confidence": ident.get("identity_confidence", ""),
        })
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--identity-csv", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--failed-csv", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    out = build(Path(args.identity_csv), Path(args.price_panel), Path(args.failed_csv))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8")
    print(out["recovery_status"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
