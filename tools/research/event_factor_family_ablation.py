"""Predeclared event-family ablation against a paired price-only baseline.

Consumes the family score columns emitted by build_pit_event_signal_panel.py.
Each family is compared only with its own same-row paired momentum baseline.
Family-to-family performance comparisons may have different coverage universes and
must not be interpreted as directly comparable without a common-universe analysis.
Research-only; no production integration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd

from tools.research.event_factor_compare_price_baseline import compare


def evaluate_family_ablations(
    signals_path: str,
    prices_path: str,
    *,
    lookback: int = 20,
    horizon: int = 20,
    cost_bps_per_side: float = 5.0,
    quantile: float = 0.2,
    min_names_per_side: int = 5,
) -> dict[str, Any]:
    signals = pd.read_csv(signals_path, dtype={"ticker": str})
    required = {"decision_at", "ticker"}
    if not required.issubset(signals.columns):
        raise ValueError(f"signals CSV requires {sorted(required)}")
    score_columns = sorted(
        column for column in signals.columns
        if column.startswith("event_score_family__")
    )
    if not score_columns:
        raise ValueError("signals CSV has no event_score_family__* columns")

    families: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="event-family-ablation-") as temp_dir:
        root = Path(temp_dir)
        for score_column in score_columns:
            family = score_column.removeprefix("event_score_family__")
            coverage_column = f"event_coverage_family__{family}"
            if coverage_column not in signals.columns:
                raise ValueError(f"missing coverage column {coverage_column}")
            frame = signals[["decision_at", "ticker", score_column, coverage_column]].copy()
            frame = frame.rename(columns={
                score_column: "event_score",
                coverage_column: "coverage_status",
            })
            input_path = root / f"{family}.csv"
            frame.to_csv(input_path, index=False)
            result = compare(
                str(input_path), prices_path,
                lookback=lookback,
                horizon=horizon,
                cost_bps_per_side=cost_bps_per_side,
                quantile=quantile,
                min_names_per_side=min_names_per_side,
            )
            families[family] = {
                "status": result.get("status"),
                "input_rows": len(frame),
                "available_score_rows": int((frame["coverage_status"].str.lower() == "available").sum()),
                "pairing": result.get("pairing"),
                "event_factor": result.get("event_factor"),
                "price_only_momentum_baseline": result.get("price_only_momentum_baseline"),
                "event_minus_momentum_mean_net_return_pct": (
                    round(
                        float(result["event_factor"]["mean_net_return_pct"])
                        - float(result["price_only_momentum_baseline"]["mean_net_return_pct"]),
                        4,
                    )
                    if result.get("event_factor", {}).get("mean_net_return_pct") is not None
                    and result.get("price_only_momentum_baseline", {}).get("mean_net_return_pct") is not None
                    else None
                ),
            }

    evaluated = sum(row["status"] == "evaluated" for row in families.values())
    return {
        "status": "evaluated" if evaluated == len(families) and families else "insufficient_data",
        "family_count": len(families),
        "evaluated_family_count": evaluated,
        "configuration": {
            "lookback": lookback,
            "horizon": horizon,
            "cost_bps_per_side": cost_bps_per_side,
            "quantile": quantile,
            "min_names_per_side": min_names_per_side,
        },
        "families": families,
        "interpretation": [
            "Each family is compared with a price-only baseline on the same paired ticker/decision rows.",
            "Different families can have different coverage universes; do not rank their returns as directly comparable without a common-universe test.",
            "Only a predeclared chronological out-of-sample test on valid point-in-time labels can support an efficacy claim.",
            "Missing family coverage remains missing and is never imputed as a neutral score.",
            "Research only; no production signal is generated.",
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
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate_family_ablations(
        args.signals, args.prices,
        lookback=args.lookback, horizon=args.horizon,
        cost_bps_per_side=args.cost_bps_per_side,
        quantile=args.quantile, min_names_per_side=args.min_names_per_side,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "family_count": result["family_count"],
        "evaluated_family_count": result["evaluated_family_count"],
        "research_only": True,
    }, indent=2, sort_keys=True))
    return 0 if result["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
