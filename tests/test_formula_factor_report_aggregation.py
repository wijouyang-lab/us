import json

import pytest

from tools.research.aggregate_formula_factor_reports import aggregate_reports


def _scenario(cost, p, net):
    return {
        "one_way_cost_bps": float(cost),
        "n_days": 30,
        "turnover_cost_available": True,
        "mean_total_turnover": 0.2,
        "mean_turnover_cost_bps": cost * 0.2,
        "turnover_aware_net_q5_q1_spread": net,
        "turnover_aware_positive_spread_day_pct": 80.0,
        "turnover_aware_spread_hac_t": 2.5,
        "turnover_aware_spread_hac_p_value": p,
        "turnover_aware_spread_by_q_value": 0.9,
        "winsorized_turnover_aware_net_q5_q1_spread": net * 0.8,
        "winsorized_mean_total_turnover": 0.2,
        "winsorized_mean_turnover_cost_bps": cost * 0.2,
        "winsorized_turnover_aware_positive_spread_day_pct": 75.0,
        "winsorized_turnover_aware_spread_hac_t": 2.2,
        "winsorized_turnover_aware_spread_hac_p_value": min(1.0, p * 2),
        "winsorized_turnover_aware_spread_by_q_value": 0.9,
    }


def _phase(offset, p, net):
    return {
        "phase_offset_sessions": offset,
        "rebalance_interval_sessions": 5,
        "n_rebalance_observations": 12,
        "gross_q5_q1_spread": net + 0.001,
        "fixed_cost_net_q5_q1_spread": net,
        "turnover_aware_net_q5_q1_spread": net,
        "mean_total_turnover": 0.2,
        "mean_turnover_cost_bps": 1.0,
        "turnover_aware_positive_spread_day_pct": 80.0,
        "turnover_aware_spread_hac_t": 2.5,
        "turnover_aware_spread_hac_p_value": p,
        "turnover_aware_spread_by_q_value": 0.9,
        "winsorized_turnover_aware_net_q5_q1_spread": net * 0.8,
        "winsorized_mean_total_turnover": 0.2,
        "winsorized_mean_turnover_cost_bps": 1.0,
        "winsorized_turnover_aware_positive_spread_day_pct": 75.0,
        "winsorized_turnover_aware_spread_hac_t": 2.2,
        "winsorized_turnover_aware_spread_hac_p_value": min(1.0, p * 2),
        "winsorized_turnover_aware_spread_by_q_value": 0.9,
        "cost_sensitivity_results": [
            _scenario(0, p / 2, net + 0.002),
            _scenario(5, p, net),
        ],
    }


def _result(candidate, p, net):
    return {
        "candidate": candidate,
        "formula": f"z_cs({candidate})",
        "family": "normalized",
        "horizon": "Forward_Return_5D",
        "n_days": 30,
        "n_stock_day_observations": 600,
        "mean_daily_ic": 0.03,
        "icir": 0.3,
        "gross_q5_q1_spread": net + 0.001,
        "net_q5_q1_spread": net,
        "positive_spread_day_pct": 70,
        "turnover_cost_available": True,
        "mean_long_turnover": 0.1,
        "mean_short_turnover": 0.1,
        "mean_total_turnover": 0.2,
        "mean_turnover_cost_bps": 1.0,
        "turnover_aware_net_q5_q1_spread": net,
        "turnover_aware_positive_spread_day_pct": 70,
        "ic_hac_p_value": p,
        "spread_hac_p_value": min(1.0, p * 1.5),
        "turnover_aware_spread_hac_p_value": min(1.0, p * 2),
        "winsorized_mean_daily_ic": 0.025,
        "winsorized_gross_q5_q1_spread": net * 0.9 + 0.001,
        "winsorized_turnover_aware_net_q5_q1_spread": net * 0.9,
        "winsorized_ic_hac_p_value": min(1.0, p * 2),
        "winsorized_spread_hac_p_value": min(1.0, p * 2.5),
        "winsorized_turnover_aware_spread_hac_p_value": min(1.0, p * 3),
        "cost_sensitivity_results": [_scenario(0, p / 2, net + 0.002), _scenario(5, p, net)],
        "low_frequency_phase_results": [_phase(0, p, net), _phase(1, p * 1.2, net * 0.9)],
    }


def _write_report(path, selected, results, *, date_max="2026-10-13"):
    report = {
        "research_only": True,
        "input": "research_backtest_sp500_pit_2y.csv",
        "rows": 222388,
        "date_min": "2024-12-09",
        "date_max": date_max,
        "cost_bps_per_leg": 5.0,
        "cost_sensitivity_one_way_bps": [0.0, 5.0],
        "selected_base_features": selected,
        "candidate_count": len(results),
        "results": results,
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_aggregator_deduplicates_overlapping_candidates_and_recorrects_joint_family(tmp_path):
    reports = tmp_path / "reports"
    first, second = reports / "family_a", reports / "family_b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    common = _result("z__ATR_Pct", 0.01, 0.02)
    only_a = _result("z__Volume_Ratio_20D", 0.04, 0.01)
    only_b = _result("z__Stock_RS_20D_vs_SPY", 0.02, 0.015)
    _write_report(first / "formula_factor_report.json", ["ATR_Pct", "Volume_Ratio_20D"], [common, only_a])
    duplicate = _result("z__ATR_Pct", 0.01, 0.02)
    duplicate["spread_fdr_q_value"] = 0.99
    _write_report(second / "formula_factor_report.json", ["ATR_Pct", "Stock_RS_20D_vs_SPY"], [duplicate, only_b])

    report = aggregate_reports(reports, tmp_path / "out")
    assert report["input_report_count"] == 2
    assert report["unique_candidates"] == 3
    assert report["unique_candidate_horizon_count"] == 3
    assert report["duplicate_candidate_horizon_rows_verified_and_deduplicated"] == 1
    common_row = next(row for row in report["results"] if row["candidate"] == "z__ATR_Pct")
    assert len(common_row["source_feature_sets"]) == 2
    assert common_row["extended_ic_by_q_value"] >= common_row["ic_hac_p_value"]
    assert common_row["extended_turnover_aware_spread_by_q_value"] >= common_row["turnover_aware_spread_hac_p_value"]
    assert common_row["cost_sensitivity_results"][0]["extended_family_turnover_aware_spread_by_q_value"] >= (
        common_row["cost_sensitivity_results"][0]["turnover_aware_spread_hac_p_value"]
    )
    assert common_row["low_frequency_phase_results"][0]["extended_turnover_aware_spread_by_q_value"] >= (
        common_row["low_frequency_phase_results"][0]["turnover_aware_spread_hac_p_value"]
    )
    assert (tmp_path / "out" / "formula_factor_extended_metrics.csv").exists()
    assert (tmp_path / "out" / "formula_factor_extended_cost_sensitivity.csv").exists()
    assert (tmp_path / "out" / "formula_factor_extended_phase_metrics.csv").exists()
    assert (tmp_path / "out" / "formula_factor_extended_phase_cost_sensitivity.csv").exists()


def test_aggregator_rejects_conflicting_duplicate_candidate_metrics(tmp_path):
    reports = tmp_path / "reports"
    first, second = reports / "family_a", reports / "family_b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    _write_report(first / "formula_factor_report.json", ["ATR_Pct"], [_result("z__ATR_Pct", 0.01, 0.02)])
    _write_report(second / "formula_factor_report.json", ["ATR_Pct"], [_result("z__ATR_Pct", 0.03, 0.02)])
    with pytest.raises(ValueError, match="duplicate candidate reports disagree"):
        aggregate_reports(reports, tmp_path / "out")


def test_aggregator_rejects_different_data_snapshots(tmp_path):
    reports = tmp_path / "reports"
    first, second = reports / "family_a", reports / "family_b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    _write_report(first / "formula_factor_report.json", ["ATR_Pct"], [_result("z__ATR_Pct", 0.01, 0.02)])
    _write_report(second / "formula_factor_report.json", ["ATR_Pct"], [_result("z__Volume_Ratio_20D", 0.03, 0.02)], date_max="2026-10-12")
    with pytest.raises(ValueError, match="do not use the same input/date range/cost setup"):
        aggregate_reports(reports, tmp_path / "out")
