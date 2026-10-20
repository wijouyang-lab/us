#!/usr/bin/env python3
"""Create a read-only, row-by-row repair plan for mixed v1/v2 price history.

The planner never edits the input history and never changes dates in-place. A
proposed +1 calendar-day mapping is only a diagnostic hypothesis; it must not
be used as an automatic repair without authoritative source verification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "phase2b.v2"
LEGACY_SCHEMA = "phase2b.v1"
VALUE_FIELDS = ("Open", "High", "Low", "Close", "Volume")
PLAN_COLUMNS = (
    "Source_Date",
    "Proposed_Date_Offset",
    "Ticker",
    "Source_Schema",
    "Reference_V2_Exists",
    "Reference_V2_Close",
    "Source_Close",
    "Close_Comparison",
    "Mismatched_Fields",
    "Missing_Source_Fields",
    "Classification",
    "Recommended_Next_Action",
)


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def _number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _same_number(left: float, right: float) -> bool:
    return abs(left - right) <= max(1e-8, abs(left) * 1e-8, abs(right) * 1e-8)


def _load_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader), list(reader.fieldnames)


def build_repair_plan(
    price_history_path: str | Path,
    offset_days: int = 1,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Classify every non-v2 row against v2 rows at the proposed target date."""
    source = Path(price_history_path)
    if not source.is_file():
        raise FileNotFoundError(f"price history file not found: {source}")
    if offset_days == 0:
        raise ValueError("offset_days must be non-zero")
    rows, headers = _load_csv(source)
    required = {"Date", "Ticker", "Close", "schema_version"}
    missing_required = sorted(required - set(headers))
    if missing_required:
        raise ValueError(f"missing required CSV columns: {missing_required}")

    refs: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    v2_dates: list[date] = []
    legacy_rows: list[dict[str, str]] = []
    invalid_ref_rows = 0

    for row in rows:
        schema = str(row.get("schema_version") or "").strip()
        parsed = parse_date(row.get("Date"))
        ticker = str(row.get("Ticker") or "").strip().upper()
        if schema == EXPECTED_SCHEMA:
            if parsed is None or not ticker:
                invalid_ref_rows += 1
                continue
            refs[(parsed.isoformat(), ticker)].append(row)
            v2_dates.append(parsed)
        else:
            legacy_rows.append(row)

    max_v2_date = max(v2_dates) if v2_dates else None
    plan: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    shifted_target_weekend_rows = 0
    target_has_reference_rows = 0
    close_compared = 0
    close_equal = 0
    close_mismatches = 0
    field_compared: Counter[str] = Counter()
    field_mismatches: Counter[str] = Counter()
    missing_source_fields: Counter[str] = Counter()

    for row in legacy_rows:
        source_text = str(row.get("Date") or "").strip()
        source_date = parse_date(source_text)
        ticker = str(row.get("Ticker") or "").strip().upper()
        schema = str(row.get("schema_version") or "<blank>").strip()
        source_close = str(row.get("Close") or "").strip()
        missing_fields = [field for field in VALUE_FIELDS if _number(row.get(field)) is None]
        for field in missing_fields:
            missing_source_fields[field] += 1

        target_date = source_date + timedelta(days=offset_days) if source_date else None
        proposed_text = target_date.isoformat() if target_date else ""
        if target_date and target_date.weekday() >= 5:
            shifted_target_weekend_rows += 1

        reference_rows = (
            refs.get((proposed_text, ticker), [])
            if target_date is not None and ticker else []
        )
        reference = reference_rows[0] if len(reference_rows) == 1 else None
        reference_exists = bool(reference_rows)
        if reference_exists:
            target_has_reference_rows += 1

        mismatched: list[str] = []
        close_comparison = "NO_REFERENCE"
        reference_close = ""
        if len(reference_rows) > 1:
            classification = "DUPLICATE_V2_REFERENCE"
            action = "STOP_AND_RESOLVE_V2_DUPLICATE"
            close_comparison = "AMBIGUOUS_REFERENCE"
        elif source_date is None or not ticker:
            classification = "INVALID_SOURCE_KEY"
            action = "REBUILD_OR_REPAIR_SOURCE_KEY"
            close_comparison = "INVALID_SOURCE_KEY"
        elif reference is None:
            if max_v2_date and target_date and target_date > max_v2_date:
                classification = "NO_V2_REFERENCE_AFTER_V2_RANGE"
                action = "FETCH_AND_VERIFY_AUTHORITATIVE_DAILY_BAR"
            else:
                classification = "NO_V2_REFERENCE_WITHIN_V2_RANGE"
                action = "VERIFY_TICKER_UNIVERSE_AND_AUTHORITATIVE_DAILY_BAR"
        else:
            for field in VALUE_FIELDS:
                source_value = _number(row.get(field))
                ref_value = _number(reference.get(field))
                if source_value is None or ref_value is None:
                    continue
                field_compared[field] += 1
                if not _same_number(source_value, ref_value):
                    mismatched.append(field)
                    field_mismatches[field] += 1

            src_close_num = _number(row.get("Close"))
            ref_close_num = _number(reference.get("Close"))
            reference_close = str(reference.get("Close") or "").strip()
            if src_close_num is None or ref_close_num is None:
                close_comparison = "UNAVAILABLE"
                classification = "V2_REFERENCE_CLOSE_UNAVAILABLE"
                action = "REBUILD_FROM_AUTHORITATIVE_DAILY_BAR"
            else:
                close_compared += 1
                if _same_number(src_close_num, ref_close_num):
                    close_equal += 1
                    close_comparison = "MATCH"
                    if mismatched:
                        classification = "CLOSE_MATCH_OTHER_FIELDS_DIFFER"
                        action = "REVIEW_FIELD_DIFFERENCES_AND_PREFER_VERIFIED_V2"
                    elif missing_fields:
                        classification = "CLOSE_MATCH_SOURCE_FIELDS_INCOMPLETE"
                        action = "REVIEW_AS_POSSIBLE_V2_DUPLICATE"
                    else:
                        classification = "CLOSE_AND_ALL_FIELDS_MATCH"
                        action = "REVIEW_AS_POSSIBLE_V2_DUPLICATE"
                else:
                    close_mismatches += 1
                    close_comparison = "MISMATCH"
                    classification = "CLOSE_MISMATCH_NEEDS_SOURCE_REVIEW"
                    action = "STOP_AND_REBUILD_FROM_AUTHORITATIVE_DAILY_BAR"

        counts[classification] += 1
        plan.append({
            "Source_Date": source_text,
            "Proposed_Date_Offset": proposed_text,
            "Ticker": ticker,
            "Source_Schema": schema,
            "Reference_V2_Exists": "true" if reference_exists else "false",
            "Reference_V2_Close": reference_close,
            "Source_Close": source_close,
            "Close_Comparison": close_comparison,
            "Mismatched_Fields": "|".join(mismatched),
            "Missing_Source_Fields": "|".join(missing_fields),
            "Classification": classification,
            "Recommended_Next_Action": action,
        })

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    summary: dict[str, Any] = {
        "read_only": True,
        "input_path": str(source),
        "input_sha256": digest,
        "rows_in_input": len(rows),
        "expected_schema": EXPECTED_SCHEMA,
        "legacy_schema_rows_planned": len(legacy_rows),
        "offset_days_tested": offset_days,
        "max_v2_date": max_v2_date.isoformat() if max_v2_date else None,
        "v2_reference_keys": len(refs),
        "invalid_v2_reference_rows": invalid_ref_rows,
        "proposed_target_weekend_rows": shifted_target_weekend_rows,
        "legacy_rows_with_v2_reference_at_proposed_date": target_has_reference_rows,
        "close_comparisons": close_compared,
        "close_equal": close_equal,
        "close_mismatches": close_mismatches,
        "fields_compared": {k: field_compared[k] for k in VALUE_FIELDS},
        "field_mismatches": {k: field_mismatches[k] for k in VALUE_FIELDS},
        "missing_source_fields": {k: missing_source_fields[k] for k in VALUE_FIELDS},
        "classifications": {k: counts[k] for k in sorted(counts)},
        "input_mutated": False,
        "automatic_repair_performed": False,
    }
    return plan, summary


def write_plan_csv(
    plan: list[dict[str, str]],
    output_path: str | Path,
    input_path: str | Path,
    overwrite: bool = False,
) -> Path:
    """Write the plan to a separate file; never overwrite the source history."""
    output = Path(output_path)
    source = Path(input_path)
    if output.resolve() == source.resolve():
        raise ValueError("refusing to write plan over the price history input")
    if output.exists() and not overwrite:
        raise FileExistsError(f"plan output already exists; refusing to overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAN_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(plan)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="只读生成 phase2b.v1 → v2 的逐行日期试配计划；不会修复输入行情文件"
    )
    parser.add_argument("--price-history", default="quant_factor_price_history.csv")
    parser.add_argument("--offset-days", type=int, default=1,
                        help="测试候选日期偏移；默认 +1 个自然日，只是诊断假设")
    parser.add_argument("--plan-csv", help="可选：另存逐行计划 CSV，不覆盖现有文件")
    parser.add_argument("--overwrite-plan", action="store_true",
                        help="允许覆盖已有计划输出文件（绝不允许覆盖输入行情）")
    args = parser.parse_args(argv)

    try:
        plan, summary = build_repair_plan(args.price_history, args.offset_days)
        if args.plan_csv:
            output = write_plan_csv(
                plan,
                args.plan_csv,
                args.price_history,
                overwrite=args.overwrite_plan,
            )
            summary["plan_csv"] = str(output)
        elif args.overwrite_plan:
            raise ValueError("--overwrite-plan requires --plan-csv")
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if summary["close_mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
