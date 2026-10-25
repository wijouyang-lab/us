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
