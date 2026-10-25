import json

import numpy as np
import pandas as pd
import pytest

from tools.research.run_formula_factor_validation import _bh_qvalues, _hac_mean_test, run


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
