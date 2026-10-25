import json

import numpy as np
import pandas as pd
import pytest

from tools.research.run_formula_factor_validation import _bh_qvalues, run


def test_bh_qvalues_are_monotone_in_p_value_order():
    p = [0.04, 0.001, 0.03, 0.8]
    q = _bh_qvalues(p)
    assert len(q) == len(p)
    assert all(0 <= x <= 1 for x in q)
    assert q[1] <= q[2] <= q[0] <= q[3]


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


def test_run_rejects_input_without_forward_labels(tmp_path):
    path = tmp_path / "input.csv"
    pd.DataFrame({"Technical_Date": ["2024-01-01"], "Signal": [1]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Forward_Return"):
        run(str(path), str(tmp_path / "out"))
