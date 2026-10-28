#!/usr/bin/env python3
"""Machine-checkable acceptance gates for resuming full-history PIT research.

This tool only evaluates an explicitly supplied audit summary. It does not
fetch, repair, or infer market data, and it never changes production state.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _number(data: dict[str, Any], key: str, *, integer: bool = False) -> float | int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a {'non-negative integer' if integer else 'number'}")
    if not math.isfinite(float(value)):
        raise ValueError(f"{key} must be finite")
    if integer and (int(value) != value or value < 0):
        raise ValueError(f"{key} must be a non-negative integer")
    return int(value) if integer else float(value)


def evaluate_gates(data: dict[str, Any]) -> dict[str, Any]:
    """Return pass/fail per predeclared gate; missing evidence fails closed."""
    expected = _number(data, "member_sessions_expected", integer=True)
    observed = _number(data, "member_sessions_observed", integer=True)
    ticker_total = _number(data, "ticker_total", integer=True)
    ticker_90 = _number(data, "tickers_at_least_90pct_coverage", integer=True)
    missing_total = _number(data, "missing_historical_tickers_total", integer=True)
    missing_verified = _number(data, "missing_historical_tickers_with_verified_identity_and_ohlcv", integer=True)
    oos_windows = _number(data, "independent_nonoverlapping_oos_windows", integer=True)

    if expected <= 0:
        raise ValueError("member_sessions_expected must be greater than zero")
    if observed > expected:
        raise ValueError("member_sessions_observed cannot exceed member_sessions_expected")
    if ticker_total <= 0 or ticker_90 > ticker_total:
        raise ValueError("ticker counts are inconsistent")
    if missing_verified > missing_total:
        raise ValueError("verified missing tickers cannot exceed missing_historical_tickers_total")

    coverage = observed / expected
    ticker_coverage = ticker_90 / ticker_total
    missing_fraction = (expected - observed) / expected
    recovery_fraction = 1.0 if missing_total == 0 else missing_verified / missing_total

    independent_source = data.get("independent_ohlcv_source_verified")
    pit_passed = data.get("pit_availability_audit_passed")
    close_diff = data.get("max_abs_close_difference_pct")
    unresolved_actions = data.get("unexplained_corporate_action_breaks")
    alpha_ci_lower = data.get("benchmark_adjusted_net_alpha_ci_lower")

    gates = {
        "member_session_coverage_ge_95pct": {
            "passed": coverage >= 0.95,
            "observed": coverage,
            "required": 0.95,
        },
        "ticker_coverage_ge_98pct": {
            "passed": ticker_coverage >= 0.98,
            "observed": ticker_coverage,
            "required": 0.98,
        },
        "unverifiable_missing_member_sessions_le_2pct": {
            "passed": missing_fraction <= 0.02,
            "observed": missing_fraction,
            "required_max": 0.02,
        },
        "missing_historical_tickers_verified_ge_98pct": {
            "passed": recovery_fraction >= 0.98,
            "observed": recovery_fraction,
            "required": 0.98,
        },
        "independent_ohlcv_source_verified": {
            "passed": independent_source is True,
            "observed": independent_source,
            "required": True,
        },
        "matched_close_difference_le_0_5pct": {
            "passed": (
                isinstance(close_diff, (int, float))
                and not isinstance(close_diff, bool)
                and math.isfinite(float(close_diff))
                and 0 <= float(close_diff) <= 0.5
            ),
            "observed": close_diff,
            "required_max_pct": 0.5,
        },
        "no_unexplained_corporate_action_breaks": {
            "passed": (
                isinstance(unresolved_actions, int)
                and not isinstance(unresolved_actions, bool)
                and unresolved_actions == 0
            ),
            "observed": unresolved_actions,
            "required": 0,
        },
        "pit_availability_audit_passed": {
            "passed": pit_passed is True,
            "observed": pit_passed,
            "required": True,
        },
        "at_least_12_independent_oos_windows": {
            "passed": oos_windows >= 12,
            "observed": oos_windows,
            "required_min": 12,
        },
        "benchmark_adjusted_net_alpha_ci_lower_gt_zero": {
            "passed": (
                isinstance(alpha_ci_lower, (int, float))
                and not isinstance(alpha_ci_lower, bool)
                and math.isfinite(float(alpha_ci_lower))
                and float(alpha_ci_lower) > 0
            ),
            "observed": alpha_ci_lower,
            "required_min_exclusive": 0,
        },
    }
    return {
        "schema_version": 1,
        "eligible_to_resume_full_history_pit_research": all(g["passed"] for g in gates.values()),
        "summary": {
            "member_session_coverage": coverage,
            "ticker_coverage_at_90pct": ticker_coverage,
            "unverifiable_member_session_fraction": missing_fraction,
            "verified_missing_ticker_fraction": recovery_fraction,
        },
        "gates": gates,
        "note": (
            "Passing these gates permits research to resume; it does not authorize "
            "production deployment or establish that a strategy has alpha."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to an audit-summary JSON file")
    parser.add_argument("--output", help="Optional path to write the JSON decision report")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = evaluate_gates(data)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["eligible_to_resume_full_history_pit_research"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
