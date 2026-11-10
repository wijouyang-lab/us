#!/usr/bin/env python3
"""Build daily membership intervals and match them to the existing price panel.

This is a coverage audit, not a price-recovery or alpha script.  Public
membership datasets are kept separate; their differences are reported rather
than merged.  No missing prices are filled.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml


def _d(value) -> date | None:
    try:
        return pd.Timestamp(value).date()
    except Exception:
        return None


def _close_open(intervals: dict[str, list], ticker: str, end: date | None, event: date | None):
    for item in reversed(intervals.get(ticker, [])):
        if item["membership_end"] is None:
            item["membership_end"] = end
            item["source_event_date"] = event
            return


def reconstruct_from_changes(initial: set[str], changes: list[dict], start: date,
                             final_date: date) -> list[dict]:
    active = set(initial)
    intervals = {t: [{"ticker": t, "membership_start": start, "membership_end": None,
                      "source_event_date": None}] for t in active}
    for ch in sorted(changes, key=lambda x: x["date"]):
        day = _d(ch["date"])
        if day is None:
            continue
        for ticker in ch.get("removed", []):
            ticker = str(ticker).upper().strip()
            if ticker in active:
                _close_open(intervals, ticker, day, day)
                active.remove(ticker)
        for ticker in ch.get("added", []):
            ticker = str(ticker).upper().strip()
            if ticker and ticker not in active:
                intervals.setdefault(ticker, []).append({
                    "ticker": ticker, "membership_start": day, "membership_end": None,
                    "source_event_date": day,
                })
                active.add(ticker)
    for ticker in active:
        _close_open(intervals, ticker, final_date, None)
    out = []
    for items in intervals.values():
        out.extend(items)
    return out


def coiltrade_intervals(path: Path, window_start: date, window_end: date) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    current = {str(x).upper() for x in data.get("current", [])}
    changes = data.get("changes", [])
    # Reverse the change log to recover the earliest known set.
    active = set(current)
    for ch in sorted(changes, key=lambda x: x.get("date", ""), reverse=True):
        if ch.get("added"):
            active.discard(str(ch["added"]).upper())
        if ch.get("removed"):
            active.add(str(ch["removed"]).upper())
    first = min((_d(x.get("date")) for x in changes if _d(x.get("date"))), default=window_start)
    # Do not extend current membership beyond the dataset's last observed change.
    last = max((_d(x.get("date")) for x in changes if _d(x.get("date"))), default=window_end)
    final = min(window_end, last)
    normalized = []
    for ch in changes:
        normalized.append({
            "date": ch.get("date"),
            "added": [ch.get("added")] if ch.get("added") else [],
            "removed": [ch.get("removed")] if ch.get("removed") else [],
        })
    return reconstruct_from_changes(active, normalized, first or window_start, final)


def shardul_intervals(directory: Path, window_start: date, window_end: date) -> list[dict]:
    files = sorted(directory.glob("*.yaml"))
    if not files:
        return []
    first = yaml.safe_load(files[0].read_text(encoding="utf-8")) or {}
    start = date(int(first.get("year", window_start.year)), 1, 1)
    active = {str(x).upper() for x in first.get("tickers_on_Jan_1", [])}
    changes = []
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for day, change in (data.get("changes") or {}).items():
            changes.append({
                "date": day,
                "removed": change.get("difference", []) or [],
                "added": change.get("union", []) or [],
            })
    last = max((_d(x["date"]) for x in changes if _d(x["date"])), default=window_end)
    return reconstruct_from_changes(active, changes, start, min(window_end, last))


def normalize(intervals: list[dict], source: str, cik_map: dict[str, str]) -> pd.DataFrame:
    out = []
    for item in intervals:
        ticker = str(item["ticker"]).upper()
        start = _d(item["membership_start"])
        end = _d(item["membership_end"])
        if not ticker or start is None:
            continue
        out.append({
            "ticker": ticker,
            "company_id": cik_map.get(ticker, ""),
            "membership_start": start.isoformat(),
            "membership_end": end.isoformat() if end else "",
            "source": source,
            "source_event_date": _d(item.get("source_event_date")).isoformat()
            if _d(item.get("source_event_date")) else "",
        })
    return pd.DataFrame(out)


def coverage(intervals: pd.DataFrame, price: pd.DataFrame, source: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    price["Date"] = pd.to_datetime(price["Date"], errors="coerce")
    price["Ticker"] = price["Ticker"].astype(str).str.upper().str.strip()
    price = price.dropna(subset=["Date"])
    calendar = sorted(price["Date"].dt.date.unique())
    by_ticker = {t: set(g["Date"].dt.date) for t, g in price.groupby("Ticker")}
    detail = []
    annual = defaultdict(lambda: {"members": set(), "expected": 0, "observed": 0,
                                   "with_price": set(), "missing": set()})
    for row in intervals.to_dict("records"):
        start = _d(row["membership_start"])
        end = _d(row["membership_end"]) if row["membership_end"] else calendar[-1]
        if start is None or end is None:
            continue
        days = [d for d in calendar if start <= d <= end]
        if not days:
            continue
        observed = sum(1 for d in days if d in by_ticker.get(row["ticker"], set()))
        detail.append({**row, "expected_days": len(days), "observed_days": observed,
                       "coverage": observed / len(days) if days else 0.0,
                       "status": "complete" if observed == len(days)
                       else ("partial" if observed > 0 else "missing")})
        for d in days:
            a = annual[d.year]
            a["members"].add(row["ticker"])
            a["expected"] += 1
            if d in by_ticker.get(row["ticker"], set()):
                a["observed"] += 1
                a["with_price"].add(row["ticker"])
            else:
                a["missing"].add(row["ticker"])
    annual_rows = [{
        "year": y, "source": source, "member_tickers": len(a["members"]),
        "member_days_expected": a["expected"], "member_days_observed": a["observed"],
        "member_day_coverage": a["observed"] / a["expected"] if a["expected"] else 0.0,
        "members_with_any_price": len(a["with_price"]),
        "members_missing_all_price": len(a["missing"]),
    } for y, a in sorted(annual.items())]
    return pd.DataFrame(detail), pd.DataFrame(annual_rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coiltrade", required=True)
    p.add_argument("--shardul-dir", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--identity-csv", required=True)
    p.add_argument("--outdir", required=True)
    args = p.parse_args(argv)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    price = pd.read_csv(args.price_panel)
    identity = pd.read_csv(args.identity_csv, dtype=str, keep_default_na=False)
    cik_map = {r["ticker"].upper(): r.get("cik", "") for _, r in identity.iterrows()}
    window_start = price["Date"].min()
    window_end = price["Date"].max()
    for source, intervals in (
        ("coiltrade", coiltrade_intervals(Path(args.coiltrade), _d(window_start), _d(window_end))),
        ("shardul", shardul_intervals(Path(args.shardul_dir), _d(window_start), _d(window_end))),
    ):
        norm = normalize(intervals, source, cik_map)
        norm.to_csv(out / f"{source}_membership_intervals.csv", index=False, encoding="utf-8")
        detail, annual = coverage(norm, price, source)
        detail.to_csv(out / f"{source}_ticker_coverage.csv", index=False, encoding="utf-8")
        annual.to_csv(out / f"{source}_annual_coverage.csv", index=False, encoding="utf-8")
        print(source, "intervals", len(norm), "tickers", norm["ticker"].nunique())
        print(annual.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
