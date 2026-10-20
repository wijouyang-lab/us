#!/usr/bin/env python3
"""Read-only audit for factor snapshot session dates and price-history schema integrity.

This utility never changes input files. Use --strict to return exit code 1 when
integrity issues are found; without --strict it always prints the complete report.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

EXPECTED_PRICE_SCHEMA = "phase2b.v2"
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _read_csv(path: Path) -> tuple[list[dict[str, str]] | None, str | None]:
    if not path.is_file():
        return None, f"file not found: {path}"
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return [], "missing CSV header"
            return list(reader), None
    except (OSError, csv.Error, UnicodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def _sorted_counts(counter: Counter) -> dict[str, int]:
    return {str(key): int(counter[key]) for key in sorted(counter, key=str)}


def _date_range(values: list[date]) -> list[str | None]:
    if not values:
        return [None, None]
    return [min(values).isoformat(), max(values).isoformat()]


def audit_snapshot(path: str | Path = "quant_factor_snapshot.csv") -> dict[str, Any]:
    """Summarize date/session-date consistency in quant_factor_snapshot.csv."""
    path = Path(path)
    rows, read_error = _read_csv(path)
    if rows is None:
        return {"path": str(path), "read_error": read_error, "rows": 0}
    if not rows and read_error:
        return {"path": str(path), "read_error": read_error, "rows": 0}

    schema_counts: Counter = Counter()
    delta_days: Counter = Counter()
    technical_weekdays: Counter = Counter()
    seen_keys: set[str] = set()
    duplicate_keys = 0
    invalid_scan_date_rows = 0
    invalid_technical_date_rows = 0
    scan_weekend_rows = 0
    technical_weekend_rows = 0
    weekend_examples: list[dict[str, str]] = []
    scan_dates: list[date] = []
    technical_dates: list[date] = []

    for row in rows:
        schema_counts[str(row.get("schema_version") or "<blank>").strip()] += 1
        scan_text = str(row.get("Scan_Date") or "").strip()
        technical_text = str(row.get("Technical_Date") or "").strip()
        ticker = str(row.get("Ticker") or "").strip().upper()
        scan_date = _parse_date(scan_text)
        technical_date = _parse_date(technical_text)

        if scan_date is None:
            invalid_scan_date_rows += 1
        else:
            scan_dates.append(scan_date)
            if scan_date.weekday() >= 5:
                scan_weekend_rows += 1

        if technical_date is None:
            invalid_technical_date_rows += 1
        else:
            technical_dates.append(technical_date)
            technical_weekdays[WEEKDAY_NAMES[technical_date.weekday()]] += 1
            if technical_date.weekday() >= 5:
                technical_weekend_rows += 1
                if len(weekend_examples) < 10:
                    weekend_examples.append({
                        "Scan_Date": scan_text,
                        "Technical_Date": technical_text,
                        "Ticker": ticker,
                    })
        if scan_date is not None and technical_date is not None:
            delta_days[f"{(scan_date - technical_date).days:+d}"] += 1

        if scan_text and ticker:
            key = f"{scan_text}|{ticker}"
            if key in seen_keys:
                duplicate_keys += 1
            seen_keys.add(key)

    return {
        "path": str(path),
        "rows": len(rows),
        "scan_date_range": _date_range(scan_dates),
        "technical_date_range": _date_range(technical_dates),
        "schema_versions": _sorted_counts(schema_counts),
        "invalid_scan_date_rows": invalid_scan_date_rows,
        "invalid_technical_date_rows": invalid_technical_date_rows,
        "scan_weekend_rows": scan_weekend_rows,
        "technical_weekend_rows": technical_weekend_rows,
        "technical_weekday_counts": _sorted_counts(technical_weekdays),
        "scan_minus_technical_calendar_days": _sorted_counts(delta_days),
        "duplicate_scan_date_ticker_keys": duplicate_keys,
        "technical_weekend_examples": weekend_examples,
        "read_error": read_error,
    }


def audit_price_history(
    path: str | Path = "quant_factor_price_history.csv",
    expected_schema: str = EXPECTED_PRICE_SCHEMA,
) -> dict[str, Any]:
    """Summarize schema versions and trading-session dates in OHLCV history."""
    path = Path(path)
    rows, read_error = _read_csv(path)
    if rows is None:
        return {"path": str(path), "read_error": read_error, "rows": 0}
    if not rows and read_error:
        return {"path": str(path), "read_error": read_error, "rows": 0}

    schema_counts: Counter = Counter()
    weekday_by_schema: dict[str, Counter] = {}
    seen_keys: set[str] = set()
    duplicate_keys = 0
    invalid_date_rows = 0
    missing_ticker_rows = 0
    invalid_close_rows = 0
    weekend_date_rows = 0
    weekend_by_schema: Counter = Counter()
    weekend_examples: list[dict[str, str]] = []
    dates: list[date] = []
    tickers: set[str] = set()

    for row in rows:
        schema = str(row.get("schema_version") or "<blank>").strip()
        schema_counts[schema] += 1
        weekday_by_schema.setdefault(schema, Counter())
        date_text = str(row.get("Date") or "").strip()
        ticker = str(row.get("Ticker") or "").strip().upper()
        parsed_date = _parse_date(date_text)

        if parsed_date is None:
            invalid_date_rows += 1
        else:
            dates.append(parsed_date)
            weekday_name = WEEKDAY_NAMES[parsed_date.weekday()]
            weekday_by_schema[schema][weekday_name] += 1
            if parsed_date.weekday() >= 5:
                weekend_date_rows += 1
                weekend_by_schema[schema] += 1
                if len(weekend_examples) < 10:
                    weekend_examples.append({
                        "Date": date_text,
                        "Ticker": ticker,
                        "schema_version": schema,
                    })

        if not ticker:
            missing_ticker_rows += 1
        else:
            tickers.add(ticker)

        try:
            close = float(str(row.get("Close") or "").strip())
            close_ok = math.isfinite(close) and close > 0
        except (TypeError, ValueError):
            close_ok = False
        if not close_ok:
            invalid_close_rows += 1

        if date_text and ticker:
            key = f"{date_text}|{ticker}"
            if key in seen_keys:
                duplicate_keys += 1
            seen_keys.add(key)

    legacy_rows = sum(
        count for schema, count in schema_counts.items() if schema != expected_schema
    )
    return {
        "path": str(path),
        "rows": len(rows),
        "date_range": _date_range(dates),
        "unique_tickers": len(tickers),
        "schema_versions": _sorted_counts(schema_counts),
        "expected_schema": expected_schema,
        "legacy_or_unexpected_schema_rows": legacy_rows,
        "invalid_date_rows": invalid_date_rows,
        "missing_ticker_rows": missing_ticker_rows,
        "invalid_or_missing_close_rows": invalid_close_rows,
        "weekend_date_rows": weekend_date_rows,
        "weekend_rows_by_schema": _sorted_counts(weekend_by_schema),
        "weekday_counts_by_schema": {
            schema: _sorted_counts(counter)
            for schema, counter in sorted(weekday_by_schema.items())
        },
        "duplicate_date_ticker_keys": duplicate_keys,
        "weekend_examples": weekend_examples,
        "read_error": read_error,
    }


def audit_files(
    snapshot_path: str | Path = "quant_factor_snapshot.csv",
    price_history_path: str | Path = "quant_factor_price_history.csv",
) -> dict[str, Any]:
    """Run the read-only audit and describe each detected blocker."""
    snapshot = audit_snapshot(snapshot_path)
    prices = audit_price_history(price_history_path)
    issues: list[str] = []

    if snapshot.get("read_error"):
        issues.append(f"snapshot read error: {snapshot['read_error']}")
    elif snapshot.get("rows", 0) == 0:
        issues.append("snapshot has no data rows")
    if snapshot.get("invalid_scan_date_rows", 0) or snapshot.get("invalid_technical_date_rows", 0):
        issues.append("snapshot contains invalid or missing scan/session dates")
    if snapshot.get("technical_weekend_rows", 0):
        issues.append(
            f"snapshot has {snapshot['technical_weekend_rows']} Technical_Date rows on weekends"
        )
    if snapshot.get("duplicate_scan_date_ticker_keys", 0):
        issues.append(
            f"snapshot has {snapshot['duplicate_scan_date_ticker_keys']} duplicate Scan_Date|Ticker keys"
        )

    if prices.get("read_error"):
        issues.append(f"price history read error: {prices['read_error']}")
    elif prices.get("rows", 0) == 0:
        issues.append("price history has no data rows")
    if prices.get("invalid_date_rows", 0) or prices.get("missing_ticker_rows", 0):
        issues.append("price history contains invalid dates or missing tickers")
    if prices.get("invalid_or_missing_close_rows", 0):
        issues.append(
            f"price history has {prices['invalid_or_missing_close_rows']} missing, invalid, or non-positive Close values"
        )
    if prices.get("duplicate_date_ticker_keys", 0):
        issues.append(
            f"price history has {prices['duplicate_date_ticker_keys']} duplicate Date|Ticker keys"
        )
    versions = set(prices.get("schema_versions", {}))
    if versions != {EXPECTED_PRICE_SCHEMA}:
        issues.append(
            f"price history schema set is {sorted(versions)}; expected only {EXPECTED_PRICE_SCHEMA}"
        )
    if prices.get("weekend_date_rows", 0):
        issues.append(
            f"price history has {prices['weekend_date_rows']} rows labelled on weekends"
        )

    return {
        "read_only": True,
        "snapshot": snapshot,
        "price_history": prices,
        "issues": issues,
        "strict_pass": not issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="只读检查量化快照的交易日日期与 OHLCV 价格历史 schema"
    )
    parser.add_argument("--snapshot", default="quant_factor_snapshot.csv")
    parser.add_argument("--price-history", default="quant_factor_price_history.csv")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="存在任何完整性问题时返回退出码 1；默认只打印审计报告",
    )
    args = parser.parse_args(argv)
    report = audit_files(args.snapshot, args.price_history)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
