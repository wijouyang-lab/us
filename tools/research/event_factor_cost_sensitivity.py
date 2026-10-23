"""Research-only event-factor sensitivity grid over holding horizons and costs.

This script does not fit or select a score. It reruns the same point-in-time
cross-sectional ranking under a declared grid, making fragility to horizon and
transaction-cost assumptions visible. Inputs and caveats are inherited from
event_factor_backtest.evaluate; no production signals are emitted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.research.event_factor_backtest import evaluate


def _int_grid(value: str, label: str) -> list[int]:
    try:
        values = sorted(set(int(part.strip()) for part in value.split(",") if part.strip()))
    except ValueError as exc:
        raise ValueError(f"{label} must be comma-separated integers") from exc
    if not values or any(v < 1 for v in values):
        raise ValueError(f"{label} must contain positive integers")
    return values


def _float_grid(value: str, label: str) -> list[float]:
    try:
        values = sorted(set(float(part.strip()) for part in value.split(",") if part.strip()))
    except ValueError as exc:
        raise ValueError(f"{label} must be comma-separated numbers") from exc
    if not values or any(v < 0 for v in values):
        raise ValueError(f"{label} must contain non-negative numbers")
    return values


def evaluate_grid(
    signals_path: str,
    prices_path: str,
    *,
    horizons: list[int],
    costs_bps: list[float],
    quantile: float = 0.2,
    min_names_per_side: int = 5,
    benchmark_path: str | None = None,
) -> dict[str, Any]:
    if not horizons or any(h < 1 for h in horizons):
        raise ValueError("horizons must be positive")
    if not costs_bps or any(c < 0 for c in costs_bps):
        raise ValueError("costs_bps must be non-negative")
    results = []
    for horizon in sorted(set(horizons)):
        for cost in sorted(set(costs_bps)):
            result = evaluate(
                signals_path,
                prices_path,
                horizon=horizon,
                cost_bps_per_side=cost,
                quantile=quantile,
                min_names_per_side=min_names_per_side,
                benchmark_path=benchmark_path,
            )
            results.append({
                "horizon_trading_observations": horizon,
                "cost_bps_per_side": cost,
                "status": result.get("status"),
                "decision_dates_tested": result.get("decision_dates_tested", 0),
                "mean_net_return_pct": result.get("mean_net_return_pct"),
                "median_net_return_pct": result.get("median_net_return_pct"),
                "positive_date_fraction": result.get("positive_date_fraction"),
                "annualized_sharpe_unadjusted": result.get("annualized_sharpe_unadjusted"),
                "max_drawdown_pct": result.get("max_drawdown_pct"),
                "cumulative_compounded_return_pct": result.get("cumulative_compounded_return_pct"),
                "excluded_unknown_coverage": result.get("excluded_unknown_coverage"),
                "excluded_missing_score": result.get("excluded_missing_score"),
            })
    evaluated = [row for row in results if row["status"] == "evaluated"]
    return {
        "schema_version": "1.0",
        "status": "evaluated" if evaluated else "insufficient_data",
        "quantile": quantile,
        "min_names_per_side": min_names_per_side,
        "grid_rows": len(results),
        "evaluated_grid_rows": len(evaluated),
        "results": results,
        "interpretation": [
            "This is sensitivity analysis, not parameter optimization or proof of alpha.",
            "Forward holding periods can overlap; reported Sharpe is unadjusted.",
            "Only point-in-time-valid scores and prices should be supplied.",
            "No score is connected to production trading decisions.",
        ],
        "research_only": True,
        "production_signal_generated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--benchmark")
    parser.add_argument("--horizons", default="5,10,20")
    parser.add_argument("--costs-bps", default="0,5,10,20")
    parser.add_argument("--quantile", type=float, default=0.2)
    parser.add_argument("--min-names-per-side", type=int, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate_grid(
        args.signals,
        args.prices,
        horizons=_int_grid(args.horizons, "horizons"),
        costs_bps=_float_grid(args.costs_bps, "costs-bps"),
        quantile=args.quantile,
        min_names_per_side=args.min_names_per_side,
        benchmark_path=args.benchmark,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2, sort_keys=True))
    return 0 if result["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
