"""Common-universe event-family ablation runner.

Filters the panel to ticker/decision rows where every configured family has
available coverage and a finite score, then delegates to the paired evaluator.
Research-only; missing event scores are never imputed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import pandas as pd

from tools.research.event_factor_family_ablation import evaluate_family_ablations


def build_common_universe(signals: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"decision_at", "ticker"}
    if not required.issubset(signals.columns):
        raise ValueError(f"signals CSV requires {sorted(required)}")
    score_columns = sorted(
        column for column in signals.columns
        if column.startswith("event_score_family__")
    )
    if not score_columns:
        raise ValueError("signals CSV has no event_score_family__* columns")

    mask = pd.Series(True, index=signals.index)
    families = []
    for score_column in score_columns:
        family = score_column.removeprefix("event_score_family__")
        coverage_column = f"event_coverage_family__{family}"
        if coverage_column not in signals.columns:
            raise ValueError(f"missing coverage column {coverage_column}")
        score = pd.to_numeric(signals[score_column], errors="coerce")
        mask &= signals[coverage_column].astype(str).str.strip().str.lower().eq("available")
        mask &= score.notna() & np.isfinite(score)
        families.append(family)

    common = signals.loc[mask].copy()
    report = {
        "input_rows": len(signals),
        "common_universe_rows": len(common),
        "excluded_rows": int(len(signals) - len(common)),
        "family_count": len(families),
        "families": families,
        "rule": "all configured families must have available coverage and finite scores for the same ticker/decision row",
        "missing_values_imputed": False,
        "research_only": True,
        "production_signal_generated": False,
    }
    return common, report


def evaluate_common_universe(
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
    common, report = build_common_universe(signals)
    with tempfile.TemporaryDirectory(prefix="event-common-universe-") as temp_dir:
        common_path = Path(temp_dir) / "common_signals.csv"
        common.to_csv(common_path, index=False)
        result = evaluate_family_ablations(
            str(common_path), prices_path,
            lookback=lookback,
            horizon=horizon,
            cost_bps_per_side=cost_bps_per_side,
            quantile=quantile,
            min_names_per_side=min_names_per_side,
        )
    result["common_universe"] = report
    result["interpretation"] = [
        "Every family is evaluated on the same ticker/decision signal rows before price-history eligibility is applied.",
        "A family can still be insufficient_data if the common universe is too small for portfolio construction.",
        "This stricter sample may be much smaller and can overrepresent events covered by every source; report coverage alongside returns.",
        "Missing values are excluded, never imputed as neutral.",
        "Research only; no production signal is generated.",
    ]
    return result


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
    result = evaluate_common_universe(
        args.signals, args.prices,
        lookback=args.lookback, horizon=args.horizon,
        cost_bps_per_side=args.cost_bps_per_side,
        quantile=args.quantile, min_names_per_side=args.min_names_per_side,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "common_universe_rows": result["common_universe"]["common_universe_rows"],
        "family_count": result["family_count"],
        "evaluated_family_count": result["evaluated_family_count"],
        "research_only": True,
    }, indent=2, sort_keys=True))
    return 0 if result["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
