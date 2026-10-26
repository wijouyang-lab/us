import json

import numpy as np
import pandas as pd
import pytest

from tools.research.run_formula_factor_validation import _bh_qvalues, _by_qvalues, _hac_mean_test, run


def test_bh_qvalues_are_monotone_in_p_value_order():
    p = [0.04, 0.001, 0.03, 0.8]
    q = _bh_qvalues(p)
    assert len(q) == len(p)
    assert all(0 <= x <= 1 for x in q)
    assert q[1] <= q[2] <= q[0] <= q[3]


def test_hac_mean_test_handles_both_ic_and_spread_metrics():
    daily = pd.DataFrame({
        "ic": np.linspace(0.02, 0.08, 40),
        "spread": np.linspace(0.001, 0.012, 40),
    })
    ic_t, ic_p = _hac_mean_test(daily, "ic", max_lag=4)
    spread_t, spread_p = _hac_mean_test(daily, "spread", max_lag=4)
    assert ic_t is not None and ic_t > 0
    assert ic_p is not None and 0 <= ic_p <= 1
    assert spread_t is not None and spread_t > 0
    assert spread_p is not None and 0 <= spread_p <= 1


def test_run_excludes_forward_returns_from_features_and_writes_reports(tmp_path):
    rng = np.random.default_rng(7)
    rows = []
    for day in pd.date_range("2024-01-01", periods=45, freq="B"):
        for i in range(20):
            x = float(rng.normal())
            y = float(rng.normal())
            rows.append({
                "Technical_Date": day,
                "Ticker": f"T{i:02}",
                "Signal": x,
                "Risk": y,
                "Forward_Return_5D": 0.01 * x + float(rng.normal(scale=0.02)),
                "Forward_Return_10D": 0.01 * y + float(rng.normal(scale=0.02)),
            })
    inp = tmp_path / "input.csv"
    out = tmp_path / "out"
    pd.DataFrame(rows).to_csv(inp, index=False)
    run(str(inp), str(out), max_base_factors=2, cost_bps=5, min_names=10)
    report = json.loads((out / "formula_factor_report.json").read_text())
    metrics = pd.read_csv(out / "formula_factor_metrics.csv")
    assert report["research_only"] is True
    assert report["candidate_count"] > 0
    assert not metrics.empty
    assert not any("Forward_Return" in str(row["candidate"]) for row in report["results"])
    assert all("ic_fdr_q_value" in row for row in report["results"])
    assert all("spread_hac_p_value" in row for row in report["results"])
    assert all("spread_fdr_q_value" in row for row in report["results"])



def test_short_folds_are_fully_embargoed_instead_of_leaking_overlapping_labels(tmp_path):
    rng = np.random.default_rng(31)
    rows = []
    # Six dates split into three two-date folds; a five-day label horizon
    # means folds 2 and 3 must be empty after embargo, not silently unpurged.
    for day in pd.date_range("2024-03-01", periods=6, freq="B"):
        for i in range(12):
            x = float(rng.normal())
            rows.append({
                "Technical_Date": day,
                "Ticker": f"T{i:02}",
                "Signal": x,
                "Forward_Return_5D": 0.01 * x + float(rng.normal(scale=0.02)),
            })
    inp, out = tmp_path / "short_folds.csv", tmp_path / "out_short_folds"
    pd.DataFrame(rows).to_csv(inp, index=False)
    run(str(inp), str(out), max_base_factors=1, cost_bps=5, min_names=10,
        requested_factors=["Signal"])
    report = json.loads((out / "formula_factor_report.json").read_text())
    row = next(r for r in report["results"] if r["candidate"] == "z__Signal")
    assert len(row["folds"]) == 3
    assert row["folds"][0]["n_days"] == 2
    assert row["folds"][1]["n_days"] == 0
    assert row["folds"][2]["n_days"] == 0


def test_run_rejects_input_without_forward_labels(tmp_path):
    path = tmp_path / "input.csv"
    pd.DataFrame({"Technical_Date": ["2024-01-01"], "Signal": [1]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Forward_Return"):
        run(str(path), str(tmp_path / "out"))

def test_requested_baselines_are_prioritized_before_feature_cap(tmp_path):
    rng = np.random.default_rng(19)
    rows = []
    for day in pd.date_range("2024-02-01", periods=12, freq="B"):
        for i in range(12):
            rows.append({
                "Technical_Date": day,
                "Ticker": f"T{i:02}",
                "Earlier_Column": float(rng.normal()),
                "ATR_Pct": float(rng.normal()),
                "Momentum_20D_Pct": float(rng.normal()),
                "Forward_Return_5D": float(rng.normal(scale=0.02)),
            })
    inp, out = tmp_path / "input.csv", tmp_path / "out"
    pd.DataFrame(rows).to_csv(inp, index=False)
    run(str(inp), str(out), max_base_factors=2, cost_bps=5, min_names=10,
        requested_factors=["ATR_Pct", "Momentum_20D_Pct"])
    report = json.loads((out / "formula_factor_report.json").read_text())
    assert report["selected_base_features"] == ["ATR_Pct", "Momentum_20D_Pct"]

# Regression coverage for mandatory fold embargo remains research-only.

def test_winsorize_target_by_date_is_cross_sectional_and_preserves_input():
    from tools.research.run_formula_factor_validation import _winsorize_target_by_date

    frame = pd.DataFrame({
        "Snapshot_Date": [pd.Timestamp("2024-01-02")] * 100
                         + [pd.Timestamp("2024-01-03")] * 100,
        "Forward_Return_5D": [0.0] * 99 + [100.0] + [0.0] * 99 + [5.0],
    })
    original = frame["Forward_Return_5D"].copy()
    clipped = _winsorize_target_by_date(frame, "Forward_Return_5D")
    assert frame["Forward_Return_5D"].equals(original)
    assert clipped.iloc[99] < 100.0
    assert clipped.iloc[199] < 5.0
    assert clipped.iloc[0] == 0.0


def test_run_reports_raw_and_winsorized_metrics_separately(tmp_path):
    rng = np.random.default_rng(88)
    rows = []
    for day in pd.date_range("2024-05-01", periods=30, freq="B"):
        for i in range(20):
            signal = float(rng.normal())
            ret = 0.01 * signal + float(rng.normal(scale=0.02))
            if day == pd.Timestamp("2024-05-15") and i == 0:
                ret = 2.0
            rows.append({
                "Technical_Date": day,
                "Ticker": f"T{i:02}",
                "Signal": signal,
                "Forward_Return_5D": ret,
            })
    inp, out = tmp_path / "input.csv", tmp_path / "out"
    pd.DataFrame(rows).to_csv(inp, index=False)
    run(str(inp), str(out), max_base_factors=1, cost_bps=5, min_names=10,
        requested_factors=["Signal"])
    report = json.loads((out / "formula_factor_report.json").read_text())
    row = next(r for r in report["results"] if r["candidate"] == "z__Signal")
    assert "net_q5_q1_spread" in row
    assert "winsorized_net_q5_q1_spread" in row
    assert "winsorized_spread_hac_p_value" in row
    assert "winsorized_spread_fdr_q_value" in row
    assert report["research_only"] is True

def test_turnover_cost_model_recognizes_stable_quintile_membership(tmp_path):
    rng = np.random.default_rng(2026)
    rows = []
    for day in pd.date_range("2024-06-03", periods=30, freq="B"):
        for i in range(20):
            signal = float(i)
            base_return = 0.02 if i >= 16 else (-0.01 if i < 4 else 0.0)
            rows.append({
                "Technical_Date": day,
                "Ticker": f"T{i:02}",
                "Signal": signal,
                "Forward_Return_5D": base_return + float(rng.normal(scale=0.008)),
            })
    inp, out = tmp_path / "stable_membership.csv", tmp_path / "stable_out"
    pd.DataFrame(rows).to_csv(inp, index=False)
    run(str(inp), str(out), max_base_factors=1, cost_bps=5, min_names=10,
        requested_factors=["Signal"])
    report = json.loads((out / "formula_factor_report.json").read_text())
    row = next(r for r in report["results"] if r["candidate"] == "z__Signal")
    assert row["turnover_cost_available"] is True
    # The JSON report deliberately rounds published metrics to six decimals.
    assert row["mean_long_turnover"] == pytest.approx(round(1 / 30, 6))
    assert row["mean_short_turnover"] == pytest.approx(round(1 / 30, 6))
    assert row["mean_total_turnover"] == pytest.approx(round(2 / 30, 6))
    assert row["mean_turnover_cost_bps"] == pytest.approx(round(10 / 30, 6))
    assert row["turnover_aware_net_q5_q1_spread"] > row["net_q5_q1_spread"]
    assert "turnover_aware_spread_hac_p_value" in row
    assert "turnover_aware_spread_fdr_q_value" in row
    assert "winsorized_turnover_aware_spread_fdr_q_value" in row


def test_turnover_cost_model_declines_duplicate_ticker_weights():
    from tools.research.run_formula_factor_validation import _attach_turnover_costs

    daily = pd.DataFrame([{
        "date": pd.Timestamp("2024-01-02"),
        "ic": 0.1,
        "spread": 0.02,
        "n": 10,
        "long_names": ("AAA", "AAA"),
        "short_names": ("BBB", "CCC"),
        "duplicate_tickers": True,
    }])
    result = _attach_turnover_costs(daily, 5)
    assert result["turnover_cost_available"].eq(False).all()
    assert result["turnover_aware_spread"].isna().all()

def test_by_qvalues_are_at_least_as_conservative_as_bh():
    p_values = [0.04, 0.001, 0.03, 0.8]
    bh = _bh_qvalues(p_values)
    by = _by_qvalues(p_values)
    assert len(by) == len(p_values)
    assert all(b >= a for a, b in zip(bh, by))
    assert all(0 <= value <= 1 for value in by)
    sorted_pairs = sorted(zip(p_values, by))
    assert [q for _p, q in sorted_pairs] == sorted(q for _p, q in sorted_pairs)


def test_low_frequency_phase_metrics_use_horizon_spaced_rebalances_and_report_by_q(tmp_path):
    rng = np.random.default_rng(20261026)
    rows = []
    for day in pd.date_range("2024-07-01", periods=60, freq="B"):
        for i in range(20):
            signal = float(i)
            noise = float(rng.normal(scale=0.01))
            base_return = 0.015 if i >= 16 else (-0.008 if i < 4 else 0.0)
            rows.append({
                "Technical_Date": day,
                "Ticker": f"T{i:02}",
                "Signal": signal,
                "Forward_Return_5D": base_return + noise,
            })
    input_path, output_dir = tmp_path / "low_frequency.csv", tmp_path / "low_frequency_out"
    pd.DataFrame(rows).to_csv(input_path, index=False)
    run(
        str(input_path), str(output_dir), max_base_factors=1, cost_bps=5,
        min_names=10, requested_factors=["Signal"],
    )

    report = json.loads((output_dir / "formula_factor_report.json").read_text())
    metrics = pd.read_csv(output_dir / "formula_factor_metrics.csv")
    phase_metrics = pd.read_csv(output_dir / "low_frequency_phase_metrics.csv")
    row = next(item for item in report["results"] if item["candidate"] == "z__Signal")

    assert row["low_frequency_rebalance_interval_sessions"] == 5
    assert row["low_frequency_phase_count"] == 5
    assert len(row["low_frequency_phase_results"]) == 5
    phase_zero = next(p for p in row["low_frequency_phase_results"] if p["phase_offset_sessions"] == 0)
    phase_one = next(p for p in row["low_frequency_phase_results"] if p["phase_offset_sessions"] == 1)
    assert phase_zero["n_rebalance_observations"] == 12
    assert phase_one["n_rebalance_observations"] == 12
    assert phase_zero["turnover_aware_spread_hac_p_value"] is not None
    assert phase_zero["turnover_aware_spread_by_q_value"] is not None
    assert phase_zero["winsorized_turnover_aware_spread_by_q_value"] is not None
    assert "low_frequency_min_net_spread_across_phases" in row
    assert "low_frequency_winsorized_min_net_spread_across_phases" in metrics.columns
    assert len(phase_metrics) == len(report["results"]) * 5
    assert (phase_metrics["rebalance_interval_sessions"] == 5).all()
    assert (
        phase_metrics["turnover_aware_spread_by_q_value"].dropna()
        >= phase_metrics["turnover_aware_spread_hac_p_value"].dropna()
    ).all()


