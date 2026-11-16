"""Recompute the two P9 denominators from frozen local inputs.

Raw files are local-only. CI is not expected to replay this; the JSON records
``CI_REPLAY_NOT_EXECUTED`` explicitly.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
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
    "p8_2/pit_coverage_by_ticker.csv": "3d5ba3e2c5479b10d4abc96a4e6755729f65629190fa887054dd26b96705094e",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_checks(base: Path) -> tuple[bool, list[dict]]:
    rows = []
    ok = True
    for rel, expected in HASHES.items():
        p = base / rel
        if not p.exists():
            rows.append({"path": rel, "expected_sha256": expected, "actual_sha256": None, "bytes": 0, "status": "MISSING"})
            ok = False
            continue
        actual = _sha(p)
        status = "MATCH" if actual == expected else "MISMATCH"
        ok &= status == "MATCH"
        rows.append({"path": rel, "expected_sha256": expected, "actual_sha256": actual, "bytes": p.stat().st_size, "status": status})
    return ok, rows


def audit_duplicate_dates(mem: pd.DataFrame) -> dict:
    """Audit duplicate dates before deduplication; never silently pick a winner."""
    work = mem.copy()
    work["_day"] = pd.to_datetime(work["date"]).dt.date
    rows = []
    for day, group in work.groupby("_day", sort=True):
        sets = [{x.strip().upper() for x in str(v).split(",") if x.strip()} for v in group["tickers"]]
        rows.append({
            "date": day.isoformat(),
            "records": len(group),
            "unique_ticker_sets": len({tuple(sorted(s)) for s in sets}),
            "same_ticker_set": len({tuple(sorted(s)) for s in sets}) == 1,
        })
    dup = [r for r in rows if r["records"] > 1]
    conflicts = [r for r in dup if not r["same_ticker_set"]]
    return {
        "rows": len(work),
        "unique_dates": len(rows),
        "duplicate_dates": len(dup),
        "duplicate_extra_rows": sum(r["records"] - 1 for r in dup),
        "conflict_dates": conflicts,
        "duplicate_dates_detail": dup,
        "passed": len(conflicts) == 0,
        "rule": "Require one ticker set per date; if conflict, block and do not choose a winner.",
    }


def run(base: Path) -> dict:
    hash_ok, hash_rows = _hash_checks(base)
    result: dict = {
        "input_files": hash_rows,
        "input_hashes_verified": hash_ok,
        "duplicate_date_audit_passed": False,
        "snapshot_replay_status": "NOT_RUN",
        "daily_replay_status": "NOT_RUN",
        "all_expected_matched": False,
        "ci_replay": False,
        "ci_replay_status": "CI_REPLAY_NOT_EXECUTED",
        "verified_tradable_recomputed": False,
        "verified_tradable_note": "981,362 is from P8.2 audit policy, not recomputed here.",
    }
    if not hash_ok:
        result["snapshot_replay_status"] = "BLOCKED_INPUT_HASH"
        result["daily_replay_status"] = "BLOCKED_INPUT_HASH"
        return result

    spy = pd.read_csv(base / "p9_1_support_resistance/spy.csv", parse_dates=["Date"])
    days = [d.date() for d in spy[(spy.Date >= "2007-05-30") & (spy.Date <= "2024-12-31")].Date]
    mem_raw = pd.read_csv(base / "historical_universe/sp500_daily.csv", parse_dates=["date"])
    mem_range = mem_raw[(mem_raw.date >= "2000-01-03") & (mem_raw.date <= "2024-12-31")]
    dup = audit_duplicate_dates(mem_range)
    result["duplicate_date_audit"] = dup
    result["duplicate_date_audit_passed"] = dup["passed"]
    if not dup["passed"]:
        result["snapshot_replay_status"] = "BLOCKED_DUPLICATE_DATE_CONFLICT"
        result["daily_replay_status"] = "BLOCKED_DUPLICATE_DATE_CONFLICT"
        return result

    mem = mem_range.drop_duplicates("date").sort_values("date")
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
    result.update({
        "snapshot_member_days": snapshot_total,
        "snapshot_valid": snapshot_valid,
        "daily_member_days": daily_total,
        "daily_valid": daily_valid,
        "snapshot_union": len(snapshot_union),
        "daily_union": len(daily_union),
        "p8_table_rows": len(p8),
        "p8_valid_tickers": int((p8["valid"] > 0).sum()),
    })
    result["matches_expected"] = {k: result[k] == v for k, v in EXPECTED.items()}
    result["snapshot_replay_status"] = "PASS" if result["matches_expected"]["snapshot_member_days"] and result["matches_expected"]["snapshot_valid"] else "FAIL"
    result["daily_replay_status"] = "PASS" if result["matches_expected"]["daily_member_days"] and result["matches_expected"]["daily_valid"] else "FAIL"
    result["all_expected_matched"] = all(result["matches_expected"].values()) and result["duplicate_date_audit_passed"]
    result["note"] = "Raw inputs are local-only; hash registration and local replay do not imply CI replay."
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
