"""Recompute the two P9 denominators from frozen local inputs.

The raw files are not in this public repository. This script is for a local
audit run with an explicit --base path; CI does not have the raw data.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd

EXPECTED = {
    "snapshot_member_days": 1_095_490,
    "snapshot_valid": 986_358,
    "daily_member_days": 2_220_522,
    "daily_valid": 2_113_080,
    "snapshot_union": 1_062,
    "daily_union": 887,
    "p8_table_rows": 1_062,
    "p8_valid_tickers": 918,
}
HASHES = {
    "historical_universe/sp500_daily.csv": "646b2e47284abfb675abebacd4a4035ba22a79ea1ccdeccce7fbe5f0e27bab3a",
    "p9_1_support_resistance/spy.csv": "4d0bdcb37f02f99a05d1be63722459ef6ec8ae740f512fdd9f85e488a86fbe62",
    "pit_data/finsaber_prices_raw.csv": "f67e3972dceefbbdf6c17b84b30957a7b83518401955fff8ae0bc4ae206fa83f",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(base: Path) -> dict:
    for rel, expected in HASHES.items():
        p = base / rel
        if _sha(p) != expected:
            raise SystemExit(f"SHA256_MISMATCH {rel}")
    spy = pd.read_csv(base / "p9_1_support_resistance/spy.csv", parse_dates=["Date"])
    days = [d.date() for d in spy[(spy.Date >= "2007-05-30") & (spy.Date <= "2024-12-31")].Date]
    mem = pd.read_csv(base / "historical_universe/sp500_daily.csv", parse_dates=["date"])
    mem = mem.drop_duplicates("date").sort_values("date")
    mem = mem[(mem.date >= "2000-01-03") & (mem.date <= "2024-12-31")]
    px = pd.read_csv(base / "pit_data/finsaber_prices_raw.csv", usecols=["date", "symbol", "adjusted_close"], parse_dates=["date"])
    px = px[(px.date >= "2000-01-03") & (px.date <= "2024-12-31")]
    px["symbol"] = px.symbol.str.upper()
    valid = {(r.date.date(), r.symbol) for r in px.itertuples() if pd.notna(r.adjusted_close) and r.adjusted_close > 0}

    snapshot_total = snapshot_valid = 0
    snapshot_union = set()
    snaps = []
    for r in mem.itertuples():
        tickers = {x.strip().upper() for x in str(r.tickers).split(",") if x.strip()}
        snaps.append((r.date.date(), tickers))
        snapshot_union |= tickers
        for t in tickers:
            snapshot_total += 1
            if (r.date.date(), t) in valid:
                snapshot_valid += 1
    sd = [x[0] for x in snaps]

    def at(d):
        i = bisect.bisect_right(sd, d) - 1
        return snaps[i][1] if i >= 0 else set()

    daily_total = daily_valid = 0
    daily_union = set()
    for d in days:
        members = at(d)
        daily_union |= members
        for t in members:
            daily_total += 1
            if (d, t) in valid:
                daily_valid += 1
    p8 = pd.read_csv(base / "p8_2/pit_coverage_by_ticker.csv")
    result = {
        "snapshot_member_days": snapshot_total,
        "snapshot_valid": snapshot_valid,
        "daily_member_days": daily_total,
        "daily_valid": daily_valid,
        "snapshot_union": len(snapshot_union),
        "daily_union": len(daily_union),
        "p8_table_rows": len(p8),
        "p8_valid_tickers": int((p8["valid"] > 0).sum()),
        "input_hashes_verified": True,
    }
    result["matches_expected"] = {k: result[k] == v for k, v in EXPECTED.items()}
    result["all_expected_matched"] = all(result["matches_expected"].values())
    result["ci_replay"] = False
    result["note"] = "Raw inputs are local-only; CI_REPLAY_NOT_EXECUTED."
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path, help="path to PR512 data/research")
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()
    result = run(args.base)
    text = json.dumps(result, indent=2)
    print(text)
    if args.json_out:
        args.json_out.write_text(text, encoding="utf-8")
    return 0 if result["all_expected_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
