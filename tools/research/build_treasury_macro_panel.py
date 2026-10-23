"""Build a strict point-in-time Treasury macro feature panel for research.

A snapshot downloaded today is not treated as available at historical decision
times. Features are emitted only when the actual snapshot retrieval timestamp is
at or before the decision timestamp, and the observation date is not after the
decision's calendar date. No forward fill across missing values or invented
historical availability is performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _aware(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(timezone.utc)


def _load_snapshot(path: str | Path, expected_type: str) -> tuple[dict[str, dict[str, Any]], datetime]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {expected_type} snapshot: {exc}") from exc
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    curve_type = metadata.get("curve_type", "nominal" if expected_type == "nominal" else None)
    if curve_type != expected_type:
        raise ValueError(f"{expected_type} snapshot must have curve_type={expected_type}")
    retrieved = _aware(metadata.get("retrieved_at_utc"), f"{expected_type} retrieved_at_utc")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"{expected_type} snapshot must contain a rows array")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = row.get("observation_date")
        if not isinstance(date, str) or not date:
            continue
        if date in indexed:
            raise ValueError(f"duplicate {expected_type} observation date: {date}")
        indexed[date] = row
    return indexed, retrieved


def build_treasury_macro_panel(
    decisions: pd.DataFrame,
    nominal_snapshot: dict[str, Any],
    real_snapshot: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if "decision_at" not in decisions.columns or decisions.empty:
        raise ValueError("decisions must be non-empty and contain decision_at")
    nominal_meta = nominal_snapshot.get("metadata", {})
    real_meta = real_snapshot.get("metadata", {})
    if nominal_meta.get("curve_type", "nominal") != "nominal":
        raise ValueError("nominal snapshot must have curve_type=nominal")
    if real_meta.get("curve_type") != "real":
        raise ValueError("real snapshot must have curve_type=real")
    nominal_retrieved = _aware(nominal_meta.get("retrieved_at_utc"), "nominal retrieved_at_utc")
    real_retrieved = _aware(real_meta.get("retrieved_at_utc"), "real retrieved_at_utc")
    nominal_rows = nominal_snapshot.get("rows")
    real_rows = real_snapshot.get("rows")
    if not isinstance(nominal_rows, list) or not isinstance(real_rows, list):
        raise ValueError("both snapshots must contain rows arrays")

    def index_rows(rows: list[Any], label: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            date = row.get("observation_date")
            if not isinstance(date, str) or not date:
                continue
            if date in result:
                raise ValueError(f"duplicate {label} observation date: {date}")
            result[date] = row
        return result

    nominal_by_date = index_rows(nominal_rows, "nominal")
    real_by_date = index_rows(real_rows, "real")
    decisions = decisions.copy()
    decisions["_decision_parsed"] = [
        _aware(value, "decision_at") for value in decisions["decision_at"].astype(str)
    ]
    records: list[dict[str, Any]] = []
    maturity_columns = {
        "nominal_2y_pct": ("nominal", "2y"),
        "nominal_3m_pct": ("nominal", "3m"),
        "nominal_10y_pct": ("nominal", "10y"),
        "real_10y_pct": ("real", "10y"),
    }
    both_available_at = max(nominal_retrieved, real_retrieved)
    eligible_decisions = 0
    for row in decisions.to_dict("records"):
        decision = row.pop("_decision_parsed")
        decision_date = decision.date().isoformat()
        nominal_ok = decision >= nominal_retrieved
        real_ok = decision >= real_retrieved
        nominal_dates = [d for d in nominal_by_date if d <= decision_date] if nominal_ok else []
        real_dates = [d for d in real_by_date if d <= decision_date] if real_ok else []
        ndate = max(nominal_dates) if nominal_dates else None
        rdate = max(real_dates) if real_dates else None
        nrow = nominal_by_date.get(ndate, {}) if ndate else {}
        rrow = real_by_date.get(rdate, {}) if rdate else {}
        ny = nrow.get("yield_pct", {})
        ry = rrow.get("yield_pct", {})
        n2, n3, n10 = ny.get("2y"), ny.get("3m"), ny.get("10y")
        r10 = ry.get("10y")
        slope = round((float(n10) - float(n2)) * 100, 4) if n10 is not None and n2 is not None else None
        front_slope = round((float(n10) - float(n3)) * 100, 4) if n10 is not None and n3 is not None else None
        breakeven = round((float(n10) - float(r10)) * 100, 4) if n10 is not None and r10 is not None and decision >= both_available_at else None
        dates = [d for d in (ndate, rdate) if d is not None]
        selected_date = min(dates) if len(dates) < 2 else min(dates)
        age = (decision.date() - datetime.fromisoformat(selected_date).date()).days if selected_date else None
        if nominal_ok or real_ok:
            eligible_decisions += 1
        record = dict(row)
        record.update({
            "treasury_nominal_observation_date": ndate,
            "treasury_real_observation_date": rdate,
            "treasury_feature_age_days": age,
            "treasury_nominal_2y_pct": n2 if nominal_ok else None,
            "treasury_nominal_3m_pct": n3 if nominal_ok else None,
            "treasury_nominal_10y_pct": n10 if nominal_ok else None,
            "treasury_nominal_2s10s_bp": slope if nominal_ok else None,
            "treasury_nominal_3m10y_bp": front_slope if nominal_ok else None,
            "treasury_real_10y_pct": r10 if real_ok else None,
            "treasury_breakeven_10y_proxy_bp": breakeven,
            "treasury_nominal_available": nominal_ok and ndate is not None,
            "treasury_real_available": real_ok and rdate is not None,
            "treasury_breakeven_available": decision >= both_available_at and ndate is not None and rdate is not None,
            "treasury_available_at_utc": max(nominal_retrieved, real_retrieved).isoformat().replace("+00:00", "Z"),
            "research_only": True,
        })
        records.append(record)
    output = pd.DataFrame(records)
    report = {
        "status": "built" if eligible_decisions else "no_pit_eligible_decisions",
        "input_decision_rows": len(decisions),
        "decision_rows_with_at_least_one_snapshot_available": eligible_decisions,
        "nominal_retrieved_at_utc": nominal_retrieved.isoformat().replace("+00:00", "Z"),
        "real_retrieved_at_utc": real_retrieved.isoformat().replace("+00:00", "Z"),
        "breakeven_available_at_utc": both_available_at.isoformat().replace("+00:00", "Z"),
        "future_or_unavailable_values_filled": False,
        "historical_first_seen_reconstructed": False,
        "research_only": True,
        "production_signal_generated": False,
        "limitations": [
            "Current historical snapshots are unavailable before their actual retrieval timestamps.",
            "Missing yields remain null; no interpolation or zero filling is performed.",
            "The nominal-minus-real spread is an inflation-compensation proxy, not a pure expected-inflation estimate.",
            "The feature age is the age of the most recent selected observation date; users should apply a predeclared staleness limit before evaluation.",
        ],
    }
    return output, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", required=True, help="CSV containing decision_at timestamps")
    parser.add_argument("--nominal", required=True, help="Nominal Treasury snapshot JSON")
    parser.add_argument("--real", required=True, help="Real Treasury snapshot JSON")
    parser.add_argument("--output", required=True, help="New CSV output path")
    parser.add_argument("--report", required=True, help="New JSON audit report path")
    args = parser.parse_args(argv)
    outputs = [Path(args.output), Path(args.report)]
    if any(path.exists() for path in outputs):
        parser.error("refusing to overwrite existing output/report")
    try:
        decisions = pd.read_csv(args.decisions, dtype=str)
        nominal = json.loads(Path(args.nominal).read_text(encoding="utf-8"))
        real = json.loads(Path(args.real).read_text(encoding="utf-8"))
        panel, report = build_treasury_macro_panel(decisions, nominal, real)
        outputs[0].parent.mkdir(parents=True, exist_ok=True)
        outputs[1].parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(outputs[0], index=False)
        outputs[1].write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Built {len(panel)} decision rows; PIT-eligible rows: {report['decision_rows_with_at_least_one_snapshot_available']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
