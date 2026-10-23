"""Evaluate event-factor performance conditional on predeclared Treasury regimes.

This is a descriptive, research-only analysis. It compares event scores with the
paired price-only momentum baseline within inverted/non-inverted 2s10s regimes.
Macro features must be available at each decision time and must pass a fixed
staleness cap. It does not tune thresholds or connect to production.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd

from tools.research.event_factor_compare_price_baseline import compare


def evaluate_macro_regimes(
    signals_path: str,
    prices_path: str,
    macro_panel_path: str,
    *,
    lookback: int = 20,
    horizon: int = 20,
    cost_bps_per_side: float = 5.0,
    quantile: float = 0.2,
    min_names_per_side: int = 5,
    max_feature_age_days: int = 5,
) -> dict[str, Any]:
    if max_feature_age_days < 0:
        raise ValueError("max_feature_age_days must be non-negative")
    signals = pd.read_csv(signals_path, dtype={"ticker": str})
    required_signals = {"decision_at", "ticker", "event_score", "coverage_status"}
    if not required_signals.issubset(signals.columns):
        raise ValueError(f"signals CSV requires {sorted(required_signals)}")
    macro = pd.read_csv(macro_panel_path, dtype={"decision_at": str})
    required_macro = {
        "decision_at", "treasury_nominal_2s10s_bp",
        "treasury_nominal_available_at_utc", "treasury_nominal_age_days",
        "treasury_nominal_available",
    }
    if not required_macro.issubset(macro.columns):
        raise ValueError(f"macro panel requires {sorted(required_macro)}")
    macro["decision_at"] = pd.to_datetime(macro["decision_at"], errors="coerce", utc=True)
    signals["decision_at"] = pd.to_datetime(signals["decision_at"], errors="coerce", utc=True)
    if macro["decision_at"].isna().any() or signals["decision_at"].isna().any():
        raise ValueError("decision_at must contain valid timestamps")
    if macro.duplicated(["decision_at"]).any():
        # The macro panel may preserve ticker columns. All rows at a decision time
        # must agree on macro fields; collapse only after validating that invariant.
        macro_fields = list(required_macro - {"decision_at"})
        for field in macro_fields:
            counts = macro.groupby("decision_at")[field].nunique(dropna=False)
            if (counts > 1).any():
                raise ValueError(f"macro feature {field} differs across rows sharing decision_at")
        macro = macro.sort_values("decision_at").drop_duplicates("decision_at")
    macro["treasury_nominal_age_days"] = pd.to_numeric(macro["treasury_nominal_age_days"], errors="coerce")
    macro["treasury_nominal_available_at_utc"] = pd.to_datetime(macro["treasury_nominal_available_at_utc"], errors="coerce", utc=True)
    macro["treasury_nominal_2s10s_bp"] = pd.to_numeric(macro["treasury_nominal_2s10s_bp"], errors="coerce")
    macro["treasury_nominal_available"] = macro["treasury_nominal_available"].astype(str).str.lower().isin({"true", "1"})
    joined = signals.merge(macro, on="decision_at", how="left", validate="many_to_one", suffixes=("", "_macro"))
    eligible = (
        joined["treasury_nominal_available"].fillna(False)
        & joined["treasury_nominal_available_at_utc"].notna()
        & (joined["decision_at"] >= joined["treasury_nominal_available_at_utc"])
        & joined["treasury_nominal_age_days"].notna()
        & (joined["treasury_nominal_age_days"] >= 0)
        & (joined["treasury_nominal_age_days"] <= max_feature_age_days)
        & joined["treasury_nominal_2s10s_bp"].notna()
    )
    joined = joined.loc[eligible].copy()
    joined["macro_regime"] = joined["treasury_nominal_2s10s_bp"].map(
        lambda value: "inverted_2s10s" if float(value) < 0 else "non_inverted_2s10s"
    )
    config = {
        "lookback": lookback,
        "horizon": horizon,
        "cost_bps_per_side": cost_bps_per_side,
        "quantile": quantile,
        "min_names_per_side": min_names_per_side,
        "max_feature_age_days": max_feature_age_days,
        "regime_rule": "inverted_2s10s if nominal 10y minus 2y < 0 bp; otherwise non_inverted_2s10s",
        "threshold_tuned": False,
    }
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="event-factor-macro-regimes-") as temp_dir:
        root = Path(temp_dir)
        for regime in ("inverted_2s10s", "non_inverted_2s10s"):
            frame = joined.loc[joined["macro_regime"] == regime, ["decision_at", "ticker", "event_score", "coverage_status"]].copy()
            frame["decision_at"] = frame["decision_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            path = root / f"{regime}.csv"
            frame.to_csv(path, index=False)
            if frame.empty:
                results[regime] = {
                    "status": "insufficient_data",
                    "signal_rows": 0,
                    "reason": "No rows passed point-in-time availability and staleness checks for this regime.",
                }
                continue
            result = compare(
                str(path), prices_path,
                lookback=lookback,
                horizon=horizon,
                cost_bps_per_side=cost_bps_per_side,
                quantile=quantile,
                min_names_per_side=min_names_per_side,
            )
            event = result.get("event_factor", {})
            baseline = result.get("price_only_momentum_baseline", {})
            ev, base = event.get("mean_net_return_pct"), baseline.get("mean_net_return_pct")
            results[regime] = {
                "status": result.get("status"),
                "signal_rows": len(frame),
                "distinct_decision_timestamps": int(frame["decision_at"].nunique()),
                "event_factor": event,
                "price_only_momentum_baseline": baseline,
                "event_minus_momentum_mean_net_return_pct": round(float(ev) - float(base), 4) if ev is not None and base is not None else None,
            }
    return {
        "status": "evaluated" if any(item.get("status") == "evaluated" for item in results.values()) else "insufficient_data",
        "configuration": config,
        "input_signal_rows": len(signals),
        "rows_after_pit_and_staleness_filter": len(joined),
        "excluded_rows": len(signals) - len(joined),
        "excluded_rows_are_not_imputed": True,
        "regimes": results,
        "research_only": True,
        "production_signal_generated": False,
        "alpha_established": False,
        "limitations": [
            "Regime splits are descriptive and can have small sample sizes.",
            "2s10s inversion threshold is predeclared at 0 bp; do not optimize it on the reported test period.",
            "The macro feature must be point-in-time eligible and within the configured age cap.",
            "This result does not establish causal effects or production-ready alpha.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--macro-panel", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--cost-bps-per-side", type=float, default=5.0)
    parser.add_argument("--quantile", type=float, default=0.2)
    parser.add_argument("--min-names-per-side", type=int, default=5)
    parser.add_argument("--max-feature-age-days", type=int, default=5)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error(f"refusing to overwrite existing output: {output}")
    try:
        result = evaluate_macro_regimes(
            args.signals, args.prices, args.macro_panel,
            lookback=args.lookback, horizon=args.horizon,
            cost_bps_per_side=args.cost_bps_per_side,
            quantile=args.quantile, min_names_per_side=args.min_names_per_side,
            max_feature_age_days=args.max_feature_age_days,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Macro-regime evaluation status: {result['status']}; output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
