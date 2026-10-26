import pandas as pd
import pytest

from tools.research.audit_formula_factor_dataset import audit_dataset


def test_audit_reports_duplicates_missingness_and_labels(tmp_path):
    frame = pd.DataFrame({
        "Technical_Date": ["2024-01-01", "2024-01-01", "2024-01-02"],
        "Ticker": ["AAA", "AAA", "BBB"],
        "ATR_Pct": [0.02, 0.03, None],
        "Forward_Return_5D": [0.01, 0.02, 1.5],
    })
    path = tmp_path / "dataset.csv"
    frame.to_csv(path, index=False)
    report = audit_dataset(str(path))
    assert report["row_count"] == 3
    assert report["duplicate_date_ticker_rows"] == 2
    assert report["unique_dates"] == 2
    assert report["missing_fraction_by_feature_or_label"]["ATR_Pct"] == pytest.approx(1 / 3)
    assert report["forward_return_summary"]["Forward_Return_5D"]["outside_abs_100pct"] == 1
    examples = report["suspicious_forward_return_examples"]["Forward_Return_5D"]
    assert len(examples) == 1
    assert examples[0]["ticker"] == "BBB"
    assert examples[0]["date"] == "2024-01-02"
    assert examples[0]["forward_return"] == 1.5
    assert any("Duplicate" in warning for warning in report["warnings"])
    assert any("exceed +/-100%" in warning for warning in report["warnings"])


def test_audit_rejects_missing_forward_labels(tmp_path):
    path = tmp_path / "dataset.csv"
    pd.DataFrame({"Technical_Date": ["2024-01-01"], "Ticker": ["AAA"], "ATR_Pct": [0.2]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Forward_Return"):
        audit_dataset(str(path))

def test_audit_groups_overlapping_extreme_labels_by_ticker(tmp_path):
    frame = pd.DataFrame({
        "Technical_Date": ["2024-01-01", "2024-01-02", "2024-01-02", "2024-01-03"],
        "Ticker": ["AAA", "AAA", "BBB", "AAA"],
        "Forward_Return_5D": [1.2, 1.5, 0.1, -1.3],
        "Forward_Return_10D": [1.1, 0.2, 0.3, -1.4],
    })
    path = tmp_path / "dataset.csv"
    frame.to_csv(path, index=False)
    report = audit_dataset(str(path))
    summaries = report["extreme_forward_returns_by_ticker"]
    assert summaries[0]["ticker"] == "AAA"
    assert summaries[0]["extreme_label_count"] == 5
    assert summaries[0]["distinct_dates"] == 3
    assert summaries[0]["labels_affected"] == ["Forward_Return_10D", "Forward_Return_5D"]
    assert summaries[0]["max_abs_forward_return"] == pytest.approx(1.5)
