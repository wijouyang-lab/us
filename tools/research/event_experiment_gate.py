#!/usr/bin/env python3
"""Fail-closed gate for the pre-registered event experiment.

This is the formal experiment entrance. It does not compute returns; it only
checks whether the pre-registered sample and configuration requirements are met.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIN_UNIQUE_EVENTS = 200
MIN_COVERAGE_DAYS = 365
MIN_READY_1D = 200
MIN_READY_5D = 200
MIN_OOS_WINDOWS = 2
REQUIRED_COSTS = {5.0, 10.0, 20.0}
REQUIRED_HORIZONS = {1, 5}
REQUIRED_MULTIPLE_TESTING = "benjamini-hochberg"


def _days(a: str, b: str) -> float:
    x = datetime.fromisoformat(a.replace("Z", "+00:00"))
    y = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return (y - x).total_seconds() / 86400


def evaluate(events: list[dict], readiness: dict, config: dict[str, Any] | None) -> dict[str, Any]:
    unique = {str(e.get("event_id")) for e in events if e.get("event_id")}
    times = sorted(str(e["first_seen_at_utc"]) for e in events if e.get("first_seen_at_utc"))
    span = _days(times[0], times[-1]) if len(times) >= 2 else 0.0
    rows = readiness.get("events") or []
    entry = sum(bool(r.get("entry_bar_date")) for r in rows)
    one = sum(bool(r.get("result_1d_date")) for r in rows)
    five = sum(bool(r.get("result_5d_date")) for r in rows)
    pending = sum(str(r.get("status", "")).startswith("pending") for r in rows)
    excluded = sum(r.get("status") == "excluded" for r in rows)
    cfg = config or {}
    reasons = []
    if len(unique) < MIN_UNIQUE_EVENTS:
        reasons.append("unique_events_below_200")
    if span < MIN_COVERAGE_DAYS:
        reasons.append("coverage_below_365_days")
    if entry < MIN_UNIQUE_EVENTS:
        reasons.append("entry_results_below_200")
    if one < MIN_READY_1D:
        reasons.append("plus_1_results_below_200")
    if five < MIN_READY_5D:
        reasons.append("plus_5_results_below_200")
    if pending:
        reasons.append("pending_event_results")
    if excluded:
        reasons.append("excluded_events_present")
    if int(cfg.get("oos_windows", 0)) < MIN_OOS_WINDOWS:
        reasons.append("oos_windows_below_2")
    if not REQUIRED_COSTS.issubset({float(x) for x in cfg.get("cost_bps", [])}):
        reasons.append("cost_sensitivity_incomplete")
    if {int(x) for x in cfg.get("horizons", [])} != REQUIRED_HORIZONS:
        reasons.append("horizons_must_be_1_and_5")
    if str(cfg.get("multiple_testing", "")).lower() != REQUIRED_MULTIPLE_TESTING:
        reasons.append("multiple_testing_not_preregistered_bh")
    if not cfg.get("time_split"):
        reasons.append("time_split_missing")
    if reasons:
        status = "pending" if pending and not excluded and len(unique) >= MIN_UNIQUE_EVENTS else "not_eligible"
        code = 2 if status == "pending" else 1
    else:
        status, code = "eligible", 0
    return {
        "status": status,
        "exit_code": code,
        "reasons": reasons,
        "sample": {
            "unique_events": len(unique),
            "coverage_start": times[0] if times else None,
            "coverage_end": times[-1] if times else None,
            "coverage_days": span,
            "entry_results": entry,
            "plus_1_results": one,
            "plus_5_results": five,
            "pending_events": pending,
            "excluded_events": excluded,
        },
        "minimum": {
            "unique_events": MIN_UNIQUE_EVENTS,
            "coverage_days": MIN_COVERAGE_DAYS,
            "entry_results": MIN_UNIQUE_EVENTS,
            "plus_1_results": MIN_READY_1D,
            "plus_5_results": MIN_READY_5D,
            "oos_windows": MIN_OOS_WINDOWS,
            "cost_bps": sorted(REQUIRED_COSTS),
            "horizons": sorted(REQUIRED_HORIZONS),
            "multiple_testing": REQUIRED_MULTIPLE_TESTING,
        },
        "config": cfg,
        "research_only": True,
        "no_alpha_result": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--readiness", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    readiness = json.loads(Path(args.readiness).read_text(encoding="utf-8"))
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = evaluate(events, readiness, config)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "exit_code", "reasons", "sample")}, indent=2, ensure_ascii=False))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
