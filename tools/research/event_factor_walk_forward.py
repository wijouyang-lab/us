"""Chronological, purged out-of-sample evaluation for event scores vs momentum.

This tool does not tune scores or parameters. It splits distinct decision timestamps
chronologically into train/validation/test blocks, purges the last horizon
decision timestamps from train and validation to reduce overlapping-label leakage,
and reports each block separately. Research-only; no production connection.
"""
from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from tools.research.event_factor_compare_price_baseline import compare


def evaluate_walk_forward(
    signals_path: str,
    prices_path: str,
    *,
    lookback: int = 20,
    horizon: int = 20,
    cost_bps_per_side: float = 5.0,
    quantile: float = 0.2,
    min_names_per_side: int = 5,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
    min_decision_times_per_split: int = 2,
) -> dict[str, Any]:
    if lookback < 2 or horizon < 1 or cost_bps_per_side < 0:
        raise ValueError("invalid lookback, horizon, or transaction cost")
    if not math.isfinite(cost_bps_per_side):
        raise ValueError("cost_bps_per_side must be finite")
    if not 0 < quantile < 0.5 or min_names_per_side < 1:
        raise ValueError("invalid quantile or min_names_per_side")
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("split fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train_fraction + validation_fraction must be less than one")
    if min_decision_times_per_split < 1:
        raise ValueError("min_decision_times_per_split must be positive")

    signals = pd.read_csv(signals_path, dtype={"ticker": str})
    required = {"decision_at", "ticker", "event_score", "coverage_status"}
    if not required.issubset(signals.columns):
        raise ValueError(f"signals CSV requires {sorted(required)}")
    decisions = pd.to_datetime(signals["decision_at"], errors="coerce", utc=True)
    if decisions.isna().any():
        raise ValueError("signals contain invalid decision_at timestamps")
    unique = sorted(decisions.unique())
    if len(unique) < 3:
        return {
            "status": "insufficient_data",
            "reason": "At least three distinct decision timestamps are required.",
            "distinct_decision_timestamps": len(unique),
            "research_only": True,
            "production_signal_generated": False,
        }

    train_end = max(1, int(len(unique) * train_fraction))
    validation_end = max(train_end + 1, int(len(unique) * (train_fraction + validation_fraction)))
    if validation_end >= len(unique):
        validation_end = len(unique) - 1
    raw_blocks = {
        "train": unique[:train_end],
        "validation": unique[train_end:validation_end],
        "test": unique[validation_end:],
    }
    # A decision's forward return can extend horizon observations into the next
    # block. Purge the end of train and validation; don't purge the final test.
    blocks: dict[str, list[pd.Timestamp]] = {}
    for name, values in raw_blocks.items():
        purge = horizon if name in {"train", "validation"} else 0
        blocks[name] = list(values[:-purge] if purge and len(values) > purge else ([] if purge else values))

    counts = {name: len(values) for name, values in blocks.items()}
    if any(count < min_decision_times_per_split for count in counts.values()):
        return {
            "status": "insufficient_data",
            "reason": "Not enough decision timestamps remain in every split after chronological purging.",
            "distinct_decision_timestamps": len(unique),
            "raw_split_counts": {name: len(values) for name, values in raw_blocks.items()},
            "purged_split_counts": counts,
            "horizon_purge_decision_timestamps": horizon,
            "research_only": True,
            "production_signal_generated": False,
        }

    config = {
        "lookback": lookback,
        "horizon": horizon,
        "cost_bps_per_side": cost_bps_per_side,
        "quantile": quantile,
        "min_names_per_side": min_names_per_side,
    }
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="event-factor-walk-forward-") as temp_dir:
        root = Path(temp_dir)
        for name, block_decisions in blocks.items():
            block = signals.loc[decisions.isin(block_decisions)].copy()
            block_path = root / f"{name}_signals.csv"
            block.to_csv(block_path, index=False)
            result = compare(
                str(block_path), prices_path,
                lookback=lookback,
                horizon=horizon,
                cost_bps_per_side=cost_bps_per_side,
                quantile=quantile,
                min_names_per_side=min_names_per_side,
            )
            event = result.get("event_factor", {})
            baseline = result.get("price_only_momentum_baseline", {})
            event_mean = event.get("mean_net_return_pct")
            baseline_mean = baseline.get("mean_net_return_pct")
            results[name] = {
                "status": result["status"],
                "decision_timestamps_in_input": len(block_decisions),
                "signal_rows": len(block),
                "first_decision_at": pd.Timestamp(block_decisions[0]).isoformat(),
                "last_decision_at": pd.Timestamp(block_decisions[-1]).isoformat(),
                "pairing": result.get("pairing"),
                "event_factor": event,
                "price_only_momentum_baseline": baseline,
                "event_minus_momentum_mean_net_return_pct": (
                    round(float(event_mean) - float(baseline_mean), 4)
                    if event_mean is not None and baseline_mean is not None else None
                ),
            }

    all_evaluated = all(row["status"] == "evaluated" for row in results.values())
    return {
        "status": "evaluated" if all_evaluated else "insufficient_data",
        "split_method": "chronological contiguous decision timestamps; fixed fractions; no parameter fitting",
        "fractions": {
            "train": train_fraction,
            "validation": validation_fraction,
            "test": 1 - train_fraction - validation_fraction,
        },
        "purge": {
            "method": "remove final decision timestamps from train and validation",
            "decision_timestamps_removed_per_nonfinal_split": horizon,
            "reason": "reduce overlapping forward-return labels across adjacent splits",
        },
        "configuration": config,
        "distinct_decision_timestamps": len(unique),
        "raw_split_counts": {name: len(values) for name, values in raw_blocks.items()},
        "purged_split_counts": counts,
        "splits": results,
        "interpretation": [
            "Only the chronological test block is the final out-of-sample result; train and validation are diagnostic.",
            "The event score must already be independently labeled and point-in-time valid.",
            "Purging is based on decision timestamps, an approximation to trading-session overlap; it does not guarantee fully independent returns.",
            "Close-price fills, overlapping holdings within each block, unadjusted Sharpe, and non-exposure-matched benchmark limitations remain.",
            "This report does not activate or generate production signals.",
        ],
        "research_only": True,
        "production_signal_generated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--cost-bps-per-side", type=float, default=5.0)
    parser.add_argument("--quantile", type=float, default=0.2)
    parser.add_argument("--min-names-per-side", type=int, default=5)
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--min-decision-times-per-split", type=int, default=2)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate_walk_forward(
        args.signals, args.prices,
        lookback=args.lookback, horizon=args.horizon,
        cost_bps_per_side=args.cost_bps_per_side,
        quantile=args.quantile, min_names_per_side=args.min_names_per_side,
        train_fraction=args.train_fraction,
        validation_fraction=args.validation_fraction,
        min_decision_times_per_split=args.min_decision_times_per_split,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "raw_split_counts": result.get("raw_split_counts"),
        "purged_split_counts": result.get("purged_split_counts"),
        "test_event_minus_momentum_mean_net_return_pct": result.get("splits", {}).get("test", {}).get("event_minus_momentum_mean_net_return_pct"),
        "research_only": True,
    }, indent=2, sort_keys=True))
    return 0 if result["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
