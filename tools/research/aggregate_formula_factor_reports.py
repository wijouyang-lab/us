"""Combine bounded PIT formula reports and re-correct the complete tested family.

Duplicate candidate/horizon rows are kept once only after underlying raw metrics
and p-values agree. The output recalculates Benjamini-Yekutieli q-values across
the combined candidate family rather than trusting within-run q-values from
separate feature batches.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

MAIN_TESTS = (
    ("ic_hac_p_value", "extended_ic_by_q_value"),
    ("spread_hac_p_value", "extended_spread_by_q_value"),
    ("turnover_aware_spread_hac_p_value", "extended_turnover_aware_spread_by_q_value"),
    ("winsorized_ic_hac_p_value", "extended_winsorized_ic_by_q_value"),
    ("winsorized_spread_hac_p_value", "extended_winsorized_spread_by_q_value"),
    ("winsorized_turnover_aware_spread_hac_p_value", "extended_winsorized_turnover_aware_spread_by_q_value"),
)
RAW_COST_P = "turnover_aware_spread_hac_p_value"
WINSORIZED_COST_P = "winsorized_turnover_aware_spread_hac_p_value"
COST_Q = "extended_family_turnover_aware_spread_by_q_value"
WINSORIZED_COST_Q = "extended_family_winsorized_turnover_aware_spread_by_q_value"


def _by_qvalues(p_values: list[float]) -> list[float]:
    """Benjamini-Yekutieli q-values under arbitrary test dependence."""
    n = len(p_values)
    if n == 0:
        return []
    harmonic = sum(1.0 / rank for rank in range(1, n + 1))
    order = sorted(range(n), key=lambda idx: p_values[idx])
    q = [1.0] * n
    running = 1.0
    for sorted_idx in range(n - 1, -1, -1):
        original_idx = order[sorted_idx]
        rank = sorted_idx + 1
        running = min(running, float(p_values[original_idx]) * n * harmonic / rank)
        q[original_idx] = min(1.0, running)
    return q


def _same_scalar(left: Any, right: Any, *, tolerance: float = 1e-6) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isfinite(float(left)) or not math.isfinite(float(right)):
            return left == right
        return abs(float(left) - float(right)) <= tolerance
    return left == right


def _assert_duplicate_results_match(left: dict[str, Any], right: dict[str, Any]) -> None:
    """Check overlapping formulas agree on raw metrics, not family-specific q-values."""
    fields = (
        "formula", "family", "n_days", "n_stock_day_observations",
        "mean_daily_ic", "gross_q5_q1_spread", "turnover_aware_net_q5_q1_spread",
        "ic_hac_p_value", "spread_hac_p_value", RAW_COST_P,
        "winsorized_mean_daily_ic", "winsorized_gross_q5_q1_spread",
        "winsorized_turnover_aware_net_q5_q1_spread", "winsorized_ic_hac_p_value",
        "winsorized_spread_hac_p_value", WINSORIZED_COST_P,
    )
    for field in fields:
        if not _same_scalar(left.get(field), right.get(field)):
            raise ValueError(
                f"duplicate candidate reports disagree for {left.get('candidate')} "
                f"/ {left.get('horizon')} field {field}: "
                f"{left.get(field)!r} != {right.get(field)!r}"
            )
    for collection in ("cost_sensitivity_results", "low_frequency_phase_results"):
        if len(left.get(collection, [])) != len(right.get(collection, [])):
            raise ValueError(
                f"duplicate candidate reports have different {collection} lengths "
                f"for {left.get('candidate')} / {left.get('horizon')}"
            )
    for lcost, rcost in zip(left.get("cost_sensitivity_results", []), right.get("cost_sensitivity_results", [])):
        for field in (
            "one_way_cost_bps", "turnover_aware_net_q5_q1_spread",
            RAW_COST_P, "winsorized_turnover_aware_net_q5_q1_spread", WINSORIZED_COST_P,
        ):
            if not _same_scalar(lcost.get(field), rcost.get(field)):
                raise ValueError(
                    f"duplicate candidate cost metrics disagree for {left.get('candidate')} "
                    f"at {lcost.get('one_way_cost_bps')} bps field {field}"
                )
    for lphase, rphase in zip(left.get("low_frequency_phase_results", []), right.get("low_frequency_phase_results", [])):
        for field in (
            "phase_offset_sessions", "n_rebalance_observations",
            "turnover_aware_net_q5_q1_spread", RAW_COST_P,
            "winsorized_turnover_aware_net_q5_q1_spread", WINSORIZED_COST_P,
        ):
            if not _same_scalar(lphase.get(field), rphase.get(field)):
                raise ValueError(
                    f"duplicate candidate low-frequency metrics disagree for {left.get('candidate')} "
                    f"phase {lphase.get('phase_offset_sessions')} field {field}"
                )
        lscenarios = lphase.get("cost_sensitivity_results", [])
        rscenarios = rphase.get("cost_sensitivity_results", [])
        if len(lscenarios) != len(rscenarios):
            raise ValueError("duplicate candidate reports have different low-frequency cost-grid lengths")
        for lcost, rcost in zip(lscenarios, rscenarios):
            for field in (
                "one_way_cost_bps", "turnover_aware_net_q5_q1_spread",
                RAW_COST_P, "winsorized_turnover_aware_net_q5_q1_spread", WINSORIZED_COST_P,
            ):
                if not _same_scalar(lcost.get(field), rcost.get(field)):
                    raise ValueError(
                        f"duplicate candidate phase/cost metrics disagree for {left.get('candidate')} "
                        f"phase {lphase.get('phase_offset_sessions')}, field {field}"
                    )


def _read_reports(reports_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    paths = sorted(reports_dir.rglob("formula_factor_report.json"))
    if len(paths) < 2:
        raise ValueError(f"expected at least two formula_factor_report.json files under {reports_dir}, found {len(paths)}")
    reports = []
    input_signature = None
    source_paths = []
    for path in paths:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read formula report {path}: {exc}") from exc
        if report.get("research_only") is not True or not isinstance(report.get("results"), list):
            raise ValueError(f"report is not a research-only formula report: {path}")
        signature = {
            key: report.get(key)
            for key in ("input", "rows", "date_min", "date_max", "cost_bps_per_leg", "cost_sensitivity_one_way_bps")
        }
        if input_signature is None:
            input_signature = signature
        elif signature != input_signature:
            raise ValueError(
                "formula reports do not use the same input/date range/cost setup: "
                f"{path} has {signature}, expected {input_signature}"
            )
        reports.append({
            "path": str(path),
            "selected_base_features": report.get("selected_base_features", []),
            "results": report["results"],
        })
        source_paths.append(str(path))
    return reports, input_signature or {}, source_paths


def _apply_main_qvalues(rows: list[dict[str, Any]]) -> None:
    horizons = sorted({str(row["horizon"]) for row in rows})
    for horizon in horizons:
        for p_col, q_col in MAIN_TESTS:
            refs = [
                row for row in rows
                if str(row["horizon"]) == horizon and row.get(p_col) is not None
            ]
            values = _by_qvalues([float(row[p_col]) for row in refs])
            for row, q in zip(refs, values):
                row[q_col] = round(q, 8)
            for row in rows:
                if str(row["horizon"]) == horizon and q_col not in row:
                    row[q_col] = None


def _apply_nested_qvalues(rows: list[dict[str, Any]], *, nested_key: str, phase_key: str | None = None) -> None:
    horizons = sorted({str(row["horizon"]) for row in rows})
    for horizon in horizons:
        for p_col, q_col in ((RAW_COST_P, COST_Q), (WINSORIZED_COST_P, WINSORIZED_COST_Q)):
            refs = []
            for row in rows:
                if str(row["horizon"]) != horizon:
                    continue
                parents: Iterable[dict[str, Any]] = [row] if phase_key is None else row.get(phase_key, [])
                for parent in parents:
                    for scenario in parent.get(nested_key, []):
                        if scenario.get(p_col) is not None:
                            refs.append((scenario, float(scenario[p_col])))
            qs = _by_qvalues([p for _scenario, p in refs])
            for (scenario, _p), q in zip(refs, qs):
                scenario[q_col] = round(q, 8)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def aggregate_reports(reports_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    reports, signature, source_paths = _read_reports(Path(reports_dir))
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    candidate_sources: dict[tuple[str, str], list[list[str]]] = {}
    source_report_counts: dict[tuple[str, str], int] = {}
    duplicate_count = 0
    for report in reports:
        features = list(report["selected_base_features"])
        for incoming in report["results"]:
            if not isinstance(incoming, dict) or not incoming.get("candidate") or not incoming.get("horizon"):
                raise ValueError("each result must contain candidate and horizon")
            key = (str(incoming["candidate"]), str(incoming["horizon"]))
            if key in unique:
                _assert_duplicate_results_match(unique[key], incoming)
                duplicate_count += 1
                source_report_counts[key] += 1
            else:
                unique[key] = json.loads(json.dumps(incoming))
                candidate_sources[key] = []
                source_report_counts[key] = 1
            if features not in candidate_sources[key]:
                candidate_sources[key].append(features)

    rows = []
    for key, row in unique.items():
        row["source_feature_sets"] = candidate_sources[key]
        row["source_report_count"] = source_report_counts[key]
        rows.append(row)
    rows.sort(key=lambda row: (str(row["horizon"]), str(row["candidate"])))

    _apply_main_qvalues(rows)
    _apply_nested_qvalues(rows, nested_key="cost_sensitivity_results")
    _apply_nested_qvalues(rows, nested_key="cost_sensitivity_results", phase_key="low_frequency_phase_results")
    # Correct baseline low-frequency phase tests across the whole candidate union.
    for horizon in sorted({str(row["horizon"]) for row in rows}):
        for p_col, q_col in (
            (RAW_COST_P, "extended_turnover_aware_spread_by_q_value"),
            (WINSORIZED_COST_P, "extended_winsorized_turnover_aware_spread_by_q_value"),
        ):
            refs = [
                (phase, float(phase[p_col]))
                for row in rows if str(row["horizon"]) == horizon
                for phase in row.get("low_frequency_phase_results", [])
                if phase.get(p_col) is not None
            ]
            qs = _by_qvalues([p for _phase, p in refs])
            for (phase, _p), q in zip(refs, qs):
                phase[q_col] = round(q, 8)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    main_csv, cost_csv, phase_csv, phase_cost_csv = [], [], [], []
    top_by_horizon: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        main_csv.append({
            key: (json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value)
            for key, value in row.items()
            if key not in ("folds", "low_frequency_phase_results", "cost_sensitivity_results")
        })
        for scenario in row.get("cost_sensitivity_results", []):
            cost_csv.append({
                "candidate": row["candidate"], "formula": row["formula"], "family": row["family"],
                "horizon": row["horizon"], "source_feature_sets": json.dumps(row["source_feature_sets"], ensure_ascii=False),
                **scenario,
            })
        for phase in row.get("low_frequency_phase_results", []):
            phase_csv.append({
                "candidate": row["candidate"], "formula": row["formula"], "family": row["family"],
                "horizon": row["horizon"], "source_feature_sets": json.dumps(row["source_feature_sets"], ensure_ascii=False),
                **{key: value for key, value in phase.items() if key != "cost_sensitivity_results"},
            })
            for scenario in phase.get("cost_sensitivity_results", []):
                phase_cost_csv.append({
                    "candidate": row["candidate"], "formula": row["formula"], "family": row["family"],
                    "horizon": row["horizon"], "phase_offset_sessions": phase["phase_offset_sessions"],
                    "rebalance_interval_sessions": phase["rebalance_interval_sessions"],
                    "source_feature_sets": json.dumps(row["source_feature_sets"], ensure_ascii=False),
                    **scenario,
                })
    for horizon in sorted({str(row["horizon"]) for row in rows}):
        best = [row for row in rows if str(row["horizon"]) == horizon]
        best.sort(
            key=lambda row: (
                float(row.get("turnover_aware_net_q5_q1_spread") or -1e9),
                -float(row.get("extended_turnover_aware_spread_by_q_value") or 1.0),
            ),
            reverse=True,
        )
        top_by_horizon[horizon] = [{
            "candidate": row["candidate"], "formula": row["formula"], "family": row["family"],
            "turnover_aware_net_q5_q1_spread": row.get("turnover_aware_net_q5_q1_spread"),
            "extended_turnover_aware_spread_by_q_value": row.get("extended_turnover_aware_spread_by_q_value"),
            "winsorized_turnover_aware_net_q5_q1_spread": row.get("winsorized_turnover_aware_net_q5_q1_spread"),
            "extended_winsorized_turnover_aware_spread_by_q_value": row.get("extended_winsorized_turnover_aware_spread_by_q_value"),
            "low_frequency_mean_net_spread_across_phases": row.get("low_frequency_mean_net_spread_across_phases"),
            "low_frequency_min_net_spread_across_phases": row.get("low_frequency_min_net_spread_across_phases"),
            "source_feature_sets": row["source_feature_sets"],
        } for row in best[:10]]

    _write_csv(out_dir / "formula_factor_extended_metrics.csv", main_csv)
    _write_csv(out_dir / "formula_factor_extended_cost_sensitivity.csv", cost_csv)
    _write_csv(out_dir / "formula_factor_extended_phase_metrics.csv", phase_csv)
    _write_csv(out_dir / "formula_factor_extended_phase_cost_sensitivity.csv", phase_cost_csv)
    result = {
        "research_only": True,
        "reports_included": source_paths,
        "input_signature": signature,
        "input_report_count": len(reports),
        "unique_candidate_horizon_count": len(rows),
        "duplicate_candidate_horizon_rows_verified_and_deduplicated": duplicate_count,
        "unique_candidates": len({row["candidate"] for row in rows}),
        "horizons": sorted({str(row["horizon"]) for row in rows}),
        "correction_method": "Benjamini-Yekutieli within horizon, jointly over unique candidates for main metrics, candidate × cost-level for daily cost scenarios, candidate × phase for low-frequency phase metrics, and candidate × phase × cost-level for low-frequency cost scenarios; raw and winsorized families are corrected separately.",
        "per_horizon_top_candidates_by_turnover_adjusted_net_spread": top_by_horizon,
        "warning": "This is an expanded exploratory formula screen. Statistical correction accounts for the combined candidate search, but does not replace independent out-of-sample evaluation, realistic execution/market-impact costs, point-in-time universe validation, or event-label validation. Cost grids and phase offsets are sensitivity diagnostics, not independent strategy observations.",
        "results": rows,
    }
    (out_dir / "formula_factor_extended_report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", required=True, help="Directory containing two family formula_factor_report.json files")
    parser.add_argument("--output-dir", required=True, help="New directory for joined report and CSVs")
    args = parser.parse_args(argv)
    try:
        report = aggregate_reports(args.reports_dir, args.output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(
        f"combined {report['input_report_count']} reports into "
        f"{report['unique_candidate_horizon_count']} unique candidate/horizon results"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
