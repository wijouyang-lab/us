#!/usr/bin/env python3
"""Audit PIT universe / delisted OHLCV feasibility from frozen trial files."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

BASE = Path("data/research/pit_data")


def load_prices():
    return pd.read_csv(BASE / "finsaber_20.csv")


def coverage_98():
    return pd.read_csv(BASE / "ticker_status_98_2026-11-04.csv")


def source_trials():
    return pd.DataFrame(json.loads((BASE / "source_trials_20.json").read_text()))


def audit():
    p = load_prices(); c = coverage_98(); s = source_trials()
    p["date"] = pd.to_datetime(p["date"])
    first_last = p.groupby("symbol").agg(rows=("date", "size"), first=("date", "min"),
                                         last=("date", "max"), last_close=("close", "last"))
    # A last close under $1 for a formerly >$10 large cap is a red flag, not a price.
    anomalies = first_last[(first_last.last_close < 1.0)].index.tolist()
    return {
        "sample_symbols": len(first_last),
        "sample_rows": int(len(p)),
        "sample_duplicate_rows": int(p.duplicated(["date", "symbol"]).sum()),
        "sample_last_dates": {k: str(v.date()) for k, v in first_last["last"].items()},
        "sample_anomalies": anomalies,
        "ticker_98_total": int(len(c)),
        "ticker_98_found": int(c.finsaber_price_found.sum()),
        "ticker_98_missing": c.loc[~c.finsaber_price_found, "ticker"].tolist(),
        "ticker_coverage": float(c.finsaber_price_found.mean()),
        "source_success_20": {
            "eodhd": int(s.eodhd_ok.sum()),
            "twelve": int(s.twelve_ok.sum()),
            "nasdaq": int(s.nasdaq_ok.sum()),
        },
        "membership_max_date": str(pd.to_datetime(pd.read_csv(BASE / "sp500_membership_raw.csv").date).max().date()),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
