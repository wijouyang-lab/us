import pandas as pd
import pytest

from tools.research.p12.pit_query import _et_end_of_day, as_of


def _panel(day: str):
    return pd.DataFrame({
        "cik": ["0000000001"], "metric": ["Revenue"], "taxonomy": ["us-gaap"],
        "tag": ["Revenues"], "unit": ["USD"], "period_start": ["2024-01-01"],
        "period_end": ["2024-12-31"], "accession": ["X1"], "filing_date": [day],
        "acceptance_datetime": [None], "value": [1],
    })


@pytest.mark.parametrize("day,expected", [
    ("2025-03-09", "2025-03-10T03:59:59Z"),
    ("2025-11-02", "2025-11-03T04:59:59Z"),
    ("2025-07-01", "2025-07-02T03:59:59Z"),
    ("2025-12-02", "2025-12-03T04:59:59Z"),
])
def test_et_end_of_day_calendar_boundaries(day, expected):
    assert _et_end_of_day(day) == pd.Timestamp(expected)


def test_spring_dst_visibility_boundary():
    p = _panel("2025-03-09")
    assert as_of(p, "1", "Revenue", "2025-03-09").iloc[0]["known_at"] == pd.Timestamp("2025-03-10T03:59:59Z")
    assert as_of(p, "1", "Revenue", "2025-03-10T03:59:58Z").empty
    assert len(as_of(p, "1", "Revenue", "2025-03-10T03:59:59Z")) == 1


def test_fall_dst_visibility_boundary():
    p = _panel("2025-11-02")
    assert as_of(p, "1", "Revenue", "2025-11-02").iloc[0]["known_at"] == pd.Timestamp("2025-11-03T04:59:59Z")
    assert as_of(p, "1", "Revenue", "2025-11-03T04:59:58Z").empty
    assert len(as_of(p, "1", "Revenue", "2025-11-03T04:59:59Z")) == 1


def test_filing_fallback_and_date_only_asof_share_boundary():
    p = _panel("2025-03-09")
    q = as_of(p, "1", "Revenue", "2025-03-09")
    assert q.iloc[0]["known_at"] == _et_end_of_day("2025-03-09")
    assert q.iloc[0]["time_precision"] == "FILING_DATE_LOW_PRECISION"


def test_full_timestamps_and_acceptance_precedence():
    p = _panel("2025-03-09")
    assert len(as_of(p, "1", "Revenue", "2025-03-10T03:59:59Z")) == 1
    assert len(as_of(p, "1", "Revenue", "2025-03-10T03:59:59+00:00")) == 1
    assert as_of(p, "1", "Revenue", "2025-03-10T03:59:58Z").empty
    with pytest.raises(ValueError, match="EXPLICIT_TIMEZONE"):
        as_of(p, "1", "Revenue", "2025-03-10T03:59:59")
    p2 = p.copy()
    p2["acceptance_datetime"] = "2025-03-10T12:00:00.000Z"
    q = as_of(p2, "1", "Revenue", "2025-03-10T12:00:00Z")
    assert q.iloc[0]["time_precision"] == "ACCEPTANCE_TIMESTAMP"
    assert q.iloc[0]["known_at"] == pd.Timestamp("2025-03-10T12:00:00Z")


def test_dst_csv_all_pass():
    import csv
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    rows = list(csv.DictReader((root / "data/research/p12_3_3_dst_boundary_tests.csv").open(encoding="utf-8")))
    assert len(rows) == 8
    assert all(r["status"] == "PASS" for r in rows)
