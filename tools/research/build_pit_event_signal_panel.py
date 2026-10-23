"""Build a research-only point-in-time event-score panel from an observed archive.

Inputs:
- --archive: JSON array of normalized, versioned event records
- --universe: CSV with ticker and optional sector; must be a historically valid universe
- --decisions: CSV with timezone-aware decision_at timestamps
- --weights: JSON object mapping event_type to finite numeric family weight
- --output: signal CSV accepted by event_factor_backtest.py
- --report: JSON audit summary

No model labels are generated. Events must already contain reviewed direction_score
and impact_score labels. This tool never connects to production scanner/trading.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from tools.research.pit_event_archive import select_event_versions_asof
from tools.research.pit_event_score import score_events_for_ticker
from tools.research.pit_event_eligibility import _parse_aware_timestamp


def _read_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc


def build_panel(
    archive_path: str,
    universe_path: str,
    decisions_path: str,
    weights_path: str,
    *,
    default_max_age_days: float = 30.0,
    max_age_days_by_type: Mapping[str, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    events = _read_json(archive_path)
    weights = _read_json(weights_path)
    if not isinstance(events, list) or any(not isinstance(row, dict) for row in events):
        raise ValueError("archive must be a JSON array of event objects")
    if not isinstance(weights, dict) or not weights:
        raise ValueError("weights must be a non-empty JSON object")
    parsed_weights: dict[str, float] = {}
    for family, raw in weights.items():
        if isinstance(raw, bool):
            raise ValueError(f"weight for {family} must be numeric")
        try:
            weight = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"weight for {family} must be numeric") from exc
        if not math.isfinite(weight):
            raise ValueError(f"weight for {family} must be finite")
        parsed_weights[str(family)] = weight

    if not math.isfinite(float(default_max_age_days)) or default_max_age_days < 0:
        raise ValueError("default_max_age_days must be finite and non-negative")
    age_config: dict[str, timedelta] = {
        family: timedelta(days=float(default_max_age_days)) for family in parsed_weights
    }
    for family, raw_days in (max_age_days_by_type or {}).items():
        if isinstance(raw_days, bool):
            raise ValueError(f"max age for {family} must be numeric")
        try:
            days = float(raw_days)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"max age for {family} must be numeric") from exc
        if not math.isfinite(days) or days < 0:
            raise ValueError(f"max age for {family} must be finite and non-negative")
        age_config[str(family)] = timedelta(days=days)

    universe = pd.read_csv(universe_path, dtype=str).fillna("")
    if "ticker" not in universe.columns or universe.empty:
        raise ValueError("universe CSV must contain at least one ticker")
    universe["ticker"] = universe["ticker"].str.strip().str.upper().str.replace("$", "", regex=False)
    if (universe["ticker"] == "").any() or universe["ticker"].duplicated().any():
        raise ValueError("universe ticker values must be non-empty and unique")
    if "sector" not in universe.columns:
        universe["sector"] = ""

    decisions = pd.read_csv(decisions_path, dtype=str)
    if "decision_at" not in decisions.columns or decisions.empty:
        raise ValueError("decisions CSV must contain decision_at rows")
    decisions["decision_at"] = decisions["decision_at"].str.strip()
    if any(_parse_aware_timestamp(value) is None for value in decisions["decision_at"]):
        raise ValueError("all decision_at values must be timezone-aware ISO-8601 timestamps")
    decisions["decision_at"] = pd.to_datetime(decisions["decision_at"], utc=True)
    decisions = decisions.drop_duplicates(["decision_at"]).sort_values("decision_at")

    versioned = [bool(row.get("event_version_id")) for row in events]
    if events and not all(versioned):
        raise ValueError("archive must contain event_version_id on every event")
    rows: list[dict[str, Any]] = []
    reason_totals: dict[str, int] = {}
    asof_event_counts: list[int] = []
    for decision in decisions["decision_at"]:
        decision_text = decision.isoformat().replace("+00:00", "Z")
        asof = select_event_versions_asof(events, decision_text) if events else []
        asof_event_counts.append(len(asof))
        for ticker_row in universe.itertuples(index=False):
            ticker = ticker_row.ticker
            sector = str(ticker_row.sector or "").strip()
            result = score_events_for_ticker(
                asof,
                ticker=ticker,
                sector=sector or None,
                decision_at=decision_text,
                family_weights=parsed_weights,
                max_age_by_type=age_config,
            )
            row = {
                "decision_at": decision_text,
                "ticker": ticker,
                "event_score": result["event_score"],
                "coverage_status": result["coverage_status"],
            }
            # Preserve independently auditable event-family scores for predeclared
            # ablation studies. A family with no eligible labeled events remains NaN.
            for family, weight in parsed_weights.items():
                family_result = score_events_for_ticker(
                    asof,
                    ticker=ticker,
                    sector=sector or None,
                    decision_at=decision_text,
                    family_weights={family: weight},
                    max_age_by_type=age_config,
                )
                row[f"event_score_family__{family}"] = family_result["event_score"]
                row[f"event_coverage_family__{family}"] = family_result["coverage_status"]
            rows.append(row)
            for reason, count in result["rejection_reason_counts"].items():
                reason_totals[reason] = reason_totals.get(reason, 0) + int(count)

    panel = pd.DataFrame(rows)
    if panel.empty:
        panel = pd.DataFrame(columns=["decision_at", "ticker", "event_score", "coverage_status"])
        for family in parsed_weights:
            panel[f"event_score_family__{family}"] = pd.Series(dtype="float64")
            panel[f"event_coverage_family__{family}"] = pd.Series(dtype="object")
    report = {
        "schema_version": "1.0",
        "decision_dates": len(decisions),
        "universe_tickers": len(universe),
        "panel_rows": len(panel),
        "available_score_rows": int((panel["coverage_status"] == "available").sum()),
        "missing_score_rows": int((panel["coverage_status"] != "available").sum()),
        "family_score_columns": {
            family: {
                "score_column": f"event_score_family__{family}",
                "coverage_column": f"event_coverage_family__{family}",
                "available_rows": int((panel.get(f"event_coverage_family__{family}", pd.Series(dtype=str)) == "available").sum()),
            }
            for family in parsed_weights
        },
        "archive_input_versions": len(events),
        "default_max_age_days": float(default_max_age_days),
        "max_age_days_by_type": {family: age.total_seconds() / 86400 for family, age in sorted(age_config.items())},
        "asof_event_count_min": min(asof_event_counts) if asof_event_counts else 0,
        "asof_event_count_max": max(asof_event_counts) if asof_event_counts else 0,
        "rejection_reason_counts": dict(sorted(reason_totals.items())),
        "limitations": [
            "No direction or impact labels are inferred; explicit reviewed labels are required.",
            "Historical decisions are valid only if archive first-seen timestamps are genuine observations made at those times.",
            "The supplied ticker/sector universe must be point-in-time correct; current constituents can create survivorship bias.",
            "An empty score is missing coverage, not a neutral score.",
            "Research only; production scanner and trading logic are untouched.",
        ],
        "research_only": True,
        "production_signal_generated": False,
    }
    return panel, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--default-max-age-days", type=float, default=30.0)
    parser.add_argument("--max-age-days-by-type", default="{}", help='JSON object overriding family freshness, e.g. {"macro_release":7,"policy":14}')
    args = parser.parse_args()
    try:
        age_overrides = json.loads(args.max_age_days_by_type)
        if not isinstance(age_overrides, dict):
            raise ValueError("--max-age-days-by-type must be a JSON object")
        panel, report = build_panel(
            args.archive, args.universe, args.decisions, args.weights,
            default_max_age_days=args.default_max_age_days,
            max_age_days_by_type=age_overrides,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    output = Path(args.output)
    report_path = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
