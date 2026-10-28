#!/usr/bin/env python3
"""Three separate, fail-closed acceptance gates for the research program.

Stages are deliberately independent in prerequisite order:

1. data research readiness  -> may resume historical data recovery;
2. strategy validation     -> requires data readiness plus OOS/cost evidence;
3. production deployment   -> requires strategy validation plus risk,
                              regression, paper-trading, and human review.

The strategy stage is NOT a prerequisite for starting data recovery.  That
would be circular: the historical data is needed to produce strategy evidence.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

MIN_MEMBER_COVERAGE = 0.95
MIN_TICKER_COVERAGE = 0.98
MAX_MISSING_FRACTION = 0.02
MIN_MISSING_TICKER_RECOVERY = 0.98
MAX_CLOSE_DIFF_PCT = 0.5
MIN_OOS_WINDOWS = 12
MAX_DRAWDOWN_PCT = 20.0
MIN_PAPER_TRADING_DAYS = 40


def _number(data: dict[str, Any], key: str, *, integer: bool = False) -> float | int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a {'non-negative integer' if integer else 'number'}")
    if not math.isfinite(float(value)):
        raise ValueError(f"{key} must be finite")
    if integer and (int(value) != value or value < 0):
        raise ValueError(f"{key} must be a non-negative integer")
    return int(value) if integer else float(value)


def _optional_number(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return float(value)


def _bool_gate(data: dict[str, Any], key: str, required: bool = True) -> dict:
    value = data.get(key)
    return {"passed": value is required, "observed": value, "required": required}


def _data_gates(data: dict[str, Any]) -> tuple[dict, dict]:
    expected = _number(data, "member_sessions_expected", integer=True)
    observed = _number(data, "member_sessions_observed", integer=True)
    ticker_total = _number(data, "ticker_total", integer=True)
    ticker_90 = _number(data, "tickers_at_least_90pct_coverage", integer=True)
    missing_total = _number(data, "missing_historical_tickers_total", integer=True)
    missing_verified = _number(
        data, "missing_historical_tickers_with_verified_identity_and_ohlcv", integer=True
    )
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
    close_diff = _optional_number(data, "max_abs_close_difference_pct")
    unresolved_actions = data.get("unexplained_corporate_action_breaks")
    gates = {
        "member_session_coverage_ge_95pct": {
            "passed": coverage >= MIN_MEMBER_COVERAGE,
            "observed": coverage,
            "required": MIN_MEMBER_COVERAGE,
        },
        "ticker_coverage_at_90pct_ge_98pct": {
            "passed": ticker_coverage >= MIN_TICKER_COVERAGE,
            "observed": ticker_coverage,
            "required": MIN_TICKER_COVERAGE,
        },
        "unverifiable_missing_member_sessions_le_2pct": {
            "passed": missing_fraction <= MAX_MISSING_FRACTION,
            "observed": missing_fraction,
            "required_max": MAX_MISSING_FRACTION,
        },
        "missing_historical_tickers_verified_ge_98pct": {
            "passed": recovery_fraction >= MIN_MISSING_TICKER_RECOVERY,
            "observed": recovery_fraction,
            "required": MIN_MISSING_TICKER_RECOVERY,
        },
        "independent_ohlcv_source_verified": _bool_gate(data, "independent_ohlcv_source_verified"),
        "matched_close_difference_le_0_5pct": {
            "passed": close_diff is not None and 0 <= close_diff <= MAX_CLOSE_DIFF_PCT,
            "observed": close_diff,
            "required_max_pct": MAX_CLOSE_DIFF_PCT,
        },
        "no_unexplained_corporate_action_breaks": {
            "passed": isinstance(unresolved_actions, int)
            and not isinstance(unresolved_actions, bool)
            and unresolved_actions == 0,
            "observed": unresolved_actions,
            "required": 0,
        },
        "pit_availability_audit_passed": _bool_gate(data, "pit_availability_audit_passed"),
    }
    summary = {
        "member_session_coverage": coverage,
        "ticker_coverage_at_90pct": ticker_coverage,
        "unverifiable_member_session_fraction": missing_fraction,
        "verified_missing_ticker_fraction": recovery_fraction,
    }
    return gates, summary


def _strategy_gates(data: dict[str, Any], data_ready: bool) -> dict:
    oos = _optional_number(data, "independent_nonoverlapping_oos_windows")
    alpha_ci = _optional_number(data, "benchmark_adjusted_net_alpha_ci_lower")
    drawdown = _optional_number(data, "max_drawdown_pct")
    return {
        "data_research_ready": {"passed": data_ready, "observed": data_ready, "required": True},
        "at_least_12_independent_oos_windows": {
            "passed": oos is not None and oos >= MIN_OOS_WINDOWS,
            "observed": oos,
            "required_min": MIN_OOS_WINDOWS,
        },
        "benchmark_adjusted_net_alpha_ci_lower_gt_zero": {
            "passed": alpha_ci is not None and alpha_ci > 0,
            "observed": alpha_ci,
            "required_min_exclusive": 0,
        },
        "max_drawdown_pct_le_20": {
            "passed": drawdown is not None and 0 <= drawdown <= MAX_DRAWDOWN_PCT,
            "observed": drawdown,
            "required_max": MAX_DRAWDOWN_PCT,
        },
        "robustness_checks_passed": _bool_gate(data, "robustness_checks_passed"),
    }


def _production_gates(data: dict[str, Any], strategy_ready: bool) -> dict:
    paper_days = _optional_number(data, "paper_trading_days")
    return {
        "strategy_validation_ready": {
            "passed": strategy_ready,
            "observed": strategy_ready,
            "required": True,
        },
        "risk_controls_verified": _bool_gate(data, "risk_controls_verified"),
        "production_regression_tests_passed": _bool_gate(data, "production_regression_tests_passed"),
        "paper_trading_days_ge_40": {
            "passed": paper_days is not None and paper_days >= MIN_PAPER_TRADING_DAYS,
            "observed": paper_days,
            "required_min": MIN_PAPER_TRADING_DAYS,
        },
        "human_review_approved": _bool_gate(data, "human_review_approved"),
    }


def evaluate_gates(data: dict[str, Any]) -> dict[str, Any]:
    """Evaluate data, strategy, and production gates independently.

    Missing evidence fails closed. Strategy/production fields are optional for
    a data-stage decision; they are simply false/not ready until supplied.
    """
    data_gates, summary = _data_gates(data)
    data_ready = all(g["passed"] for g in data_gates.values())
    strategy_gates = _strategy_gates(data, data_ready)
    strategy_ready = all(g["passed"] for g in strategy_gates.values())
    production_gates = _production_gates(data, strategy_ready)
    production_ready = all(g["passed"] for g in production_gates.values())
    return {
        "schema_version": 2,
        "stages": {
            "data_research": {
                "ready": data_ready,
                "gates": data_gates,
                "summary": summary,
                "meaning": "May resume historical data recovery; no strategy evidence implied.",
            },
            "strategy_validation": {
                "ready": strategy_ready,
                "gates": strategy_gates,
                "meaning": "May validate a strategy; requires data readiness and OOS/cost evidence.",
            },
            "production_deployment": {
                "ready": production_ready,
                "gates": production_gates,
                "meaning": "May consider deployment only after strategy, risk, regression, paper, and review gates.",
            },
        },
        "eligible_to_resume_full_history_pit_research": data_ready,
        "eligible_to_run_strategy_validation": data_ready,
        "strategy_validation_ready": strategy_ready,
        "production_deployment_ready": production_ready,
        "note": (
            "Data recovery is gated only by data quality. Strategy validation is a "
            "separate downstream gate. Passing any gate does not authorize production."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to an audit-summary JSON file")
    parser.add_argument("--output", help="Optional path to write the JSON decision report")
    parser.add_argument(
        "--require-stage",
        choices=("data", "strategy", "production"),
        default="data",
        help="Exit 0 only when the selected stage is ready (default: data)",
    )
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = evaluate_gates(data)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    key = {
        "data": "eligible_to_resume_full_history_pit_research",
        "strategy": "strategy_validation_ready",
        "production": "production_deployment_ready",
    }[args.require_stage]
    return 0 if result[key] else 1


if __name__ == "__main__":
    raise SystemExit(main())
