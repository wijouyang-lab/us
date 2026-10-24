"""Build a point-in-time panel from prospective BLS API snapshots."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

SERIES_COLUMNS = {
    "CUSR0000SA0": "bls_cpi_all_items_sa",
    "CUSR0000SA0L1E": "bls_cpi_less_food_energy_sa",
    "CES0000000001": "bls_total_nonfarm_employment",
    "LNS14000000": "bls_unemployment_rate",
    "CES0500000003": "bls_average_hourly_earnings_private",
}


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


def build_bls_macro_panel(
    decisions: pd.DataFrame,
    snapshots: list[dict[str, Any]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if "decision_at" not in decisions.columns or decisions.empty:
        raise ValueError("decisions must be non-empty and contain decision_at")
    indexed = []
    seen_times: set[datetime] = set()
    for snapshot in snapshots:
        metadata = snapshot.get("metadata", {}) if isinstance(snapshot, dict) else {}
        if metadata.get("source") != "us_bureau_of_labor_statistics_public_api":
            raise ValueError("snapshot source must be us_bureau_of_labor_statistics_public_api")
        retrieved = _aware(metadata.get("retrieved_at_utc"), "retrieved_at_utc")
        if retrieved in seen_times:
            raise ValueError(f"duplicate BLS snapshot retrieval timestamp: {retrieved.isoformat()}")
        seen_times.add(retrieved)
        series_rows = snapshot.get("series")
        if not isinstance(series_rows, list):
            raise ValueError("BLS snapshot must contain a series array")
        by_id = {str(row.get("series_id")): row for row in series_rows if isinstance(row, dict)}
        indexed.append((retrieved, metadata.get("source_payload_sha256"), by_id))
    indexed.sort(key=lambda item: item[0])

    source_decisions = decisions.copy()
    source_decisions["_decision"] = [
        _aware(value, "decision_at") for value in source_decisions["decision_at"].astype(str)
    ]
    output = []
    eligible_rows = 0
    for source_row in source_decisions.to_dict("records"):
        decision = source_row.pop("_decision")
        available = [snap for snap in indexed if snap[0] <= decision]
        record = dict(source_row)
        if available:
            retrieved, payload_hash, by_id = available[-1]
            age_days = (decision - retrieved).total_seconds() / 86400
            eligible_rows += 1
        else:
            retrieved, payload_hash, by_id, age_days = None, None, {}, None
        record.update({
            "bls_snapshot_retrieved_at_utc": retrieved.isoformat().replace("+00:00", "Z") if retrieved else None,
            "bls_snapshot_age_days": round(age_days, 6) if age_days is not None else None,
            "bls_source_payload_sha256": payload_hash,
            "bls_snapshot_available": retrieved is not None,
            "research_only": True,
        })
        for series_id, column in SERIES_COLUMNS.items():
            row = by_id.get(series_id, {})
            latest = row.get("latest_observation") if isinstance(row, dict) else None
            value = latest.get("value") if isinstance(latest, dict) else None
            period = latest.get("observation_period") if isinstance(latest, dict) else None
            record[column] = value
            record[f"{column}_observation_period"] = period
            record[f"{column}_available"] = bool(row.get("value_available")) if isinstance(row, dict) and retrieved else False
        output.append(record)
    panel = pd.DataFrame(output)
    report = {
        "status": "built" if eligible_rows else "no_pit_eligible_snapshots",
        "decision_rows": len(decisions),
        "rows_with_snapshot_available": eligible_rows,
        "snapshot_count": len(indexed),
        "earliest_snapshot_available_at_utc": indexed[0][0].isoformat().replace("+00:00", "Z") if indexed else None,
        "latest_snapshot_available_at_utc": indexed[-1][0].isoformat().replace("+00:00", "Z") if indexed else None,
        "future_snapshots_used": False,
        "historical_vintages_reconstructed": False,
        "consensus_surprises_available": False,
        "research_only": True,
        "production_signal_generated": False,
        "limitations": [
            "A decision can only use the latest snapshot actually retrieved by that decision timestamp.",
            "BLS API values may be revised; this panel uses the snapshot value observed at retrieval and does not reconstruct historical revisions.",
            "No pre-release consensus or surprise values are present.",
            "A small number of prospective snapshots is not a historical backtest dataset.",
        ],
    }
    return panel, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", required=True, help="CSV containing decision_at timestamps")
    parser.add_argument("--snapshot-dir", required=True, help="Directory containing bls_macro_series_*.json snapshots")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    outputs = [Path(args.output), Path(args.report)]
    if any(path.exists() for path in outputs):
        parser.error("refusing to overwrite existing output or report")
    try:
        decisions = pd.read_csv(args.decisions, dtype=str)
        snapshot_paths = sorted(Path(args.snapshot_dir).glob("bls_macro_series_*.json"))
        snapshots = [json.loads(path.read_text(encoding="utf-8")) for path in snapshot_paths]
        panel, report = build_bls_macro_panel(decisions, snapshots)
        outputs[0].parent.mkdir(parents=True, exist_ok=True)
        outputs[1].parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(outputs[0], index=False)
        outputs[1].write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Built {len(panel)} decision rows; rows with PIT-eligible BLS snapshots: {report['rows_with_snapshot_available']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
