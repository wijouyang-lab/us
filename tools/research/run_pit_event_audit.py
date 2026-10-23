"""Command-line runner for the research-only point-in-time event audit.

Example:
python -m tools.research.run_pit_event_audit \
  --input normalized_events.json \
  --decision-at 2026-10-15T13:00:00Z \
  --max-age-days-by-type '{"macro_release":2,"earnings":3}' \
  --output audit_report.json

Input must be a JSON array of normalized event objects. This command reads local
files only and never modifies production scanner or trading behavior.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any

from tools.research.pit_event_eligibility import _parse_aware_timestamp
from tools.research.pit_event_research_pipeline import build_event_research_report


def load_event_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSON array of event objects, rejecting ambiguous input shapes."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON input: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("input JSON must be an array of event objects")
    if any(not isinstance(row, dict) for row in payload):
        raise ValueError("every input array item must be a JSON object")
    return payload


def parse_max_age_days(raw: str | None) -> dict[str, timedelta]:
    """Parse JSON mapping event type to a finite, non-negative number of days."""
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"max-age config must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("max-age config must be a JSON object")
    result: dict[str, timedelta] = {}
    for event_type, days in payload.items():
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("max-age event type must be a non-empty string")
        if isinstance(days, bool) or not isinstance(days, (int, float)):
            raise ValueError(f"max age for {event_type} must be a number of days")
        if not math.isfinite(days) or days < 0:
            raise ValueError(f"max age for {event_type} must be finite and non-negative")
        result[event_type] = timedelta(days=float(days))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to normalized event JSON array")
    parser.add_argument("--decision-at", required=True, help="Timezone-aware ISO-8601 decision timestamp")
    parser.add_argument(
        "--max-age-days-by-type",
        default="{}",
        help='JSON object such as {"macro_release":2,"earnings":3}',
    )
    parser.add_argument(
        "--expected-sources",
        default="",
        help="Optional comma-separated source IDs that must be present, e.g. bls_cpi_rss,federal_reserve_press_rss",
    )
    parser.add_argument("--output", help="Optional report path; stdout when omitted")
    args = parser.parse_args(argv)

    try:
        if _parse_aware_timestamp(args.decision_at) is None:
            raise ValueError("--decision-at must be a timezone-aware ISO-8601 timestamp")
        events = load_event_rows(args.input)
        max_age = parse_max_age_days(args.max_age_days_by_type)
        expected_sources = [item.strip() for item in args.expected_sources.split(",") if item.strip()]
        report = build_event_research_report(
            events,
            args.decision_at,
            max_age_by_type=max_age,
            expected_sources=expected_sources,
        )
        serialized = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            Path(args.output).write_text(serialized, encoding="utf-8")
        else:
            sys.stdout.write(serialized)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
