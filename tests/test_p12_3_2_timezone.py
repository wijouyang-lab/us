import pandas as pd

from tools.research.p12.pit_query import as_of


def test_edt_filing_date_uses_eastern_end_of_day():
    panel = pd.DataFrame({
        "cik": ["0000000001"] * 3,
        "metric": ["Revenue"] * 3,
        "taxonomy": ["us-gaap"] * 3,
        "tag": ["Revenues"] * 3,
        "unit": ["USD"] * 3,
        "period_start": ["2024-01-01", "2024-04-01", "2024-07-01"],
        "period_end": ["2024-03-31", "2024-06-30", "2024-09-30"],
        "accession": ["A1", "A2", "A3"],
        "filing_date": ["2024-04-15", "2024-07-01", "2024-10-01"],
        "acceptance_datetime": [None, None, None],
        "value": [1, 2, 3],
    })
    q = as_of(panel, "1", "Revenue", "2024-07-01")
    assert set(q.accession) == {"A1", "A2"}
    assert q[q.accession == "A2"].iloc[0]["known_at"] == pd.Timestamp("2024-07-02T03:59:59Z")
    assert q[q.accession == "A2"].iloc[0]["time_precision"] == "FILING_DATE_LOW_PRECISION"
    q_before = as_of(panel, "1", "Revenue", "2024-07-02T03:59:58Z")
    assert "A2" not in set(q_before.accession)


def test_est_filing_date_uses_eastern_end_of_day():
    panel = pd.DataFrame({
        "cik": ["0000000002"], "metric": ["Assets"], "taxonomy": ["us-gaap"],
        "tag": ["Assets"], "unit": ["USD"], "period_start": [None], "period_end": ["2024-09-30"],
        "accession": ["B1"], "filing_date": ["2024-12-02"], "acceptance_datetime": [None], "value": [1],
    })
    q = as_of(panel, "2", "Assets", "2024-12-02")
    assert q.iloc[0]["known_at"] == pd.Timestamp("2024-12-03T04:59:59Z")
    assert as_of(panel, "2", "Assets", "2024-12-03T04:59:58Z").empty


def test_acceptance_timestamp_wins_and_timezone_required():
    panel = pd.DataFrame({
        "cik": ["0000000003"], "metric": ["Revenue"], "taxonomy": ["us-gaap"],
        "tag": ["Revenues"], "unit": ["USD"], "period_start": ["2024-01-01"], "period_end": ["2024-03-31"],
        "accession": ["C1"], "filing_date": ["2024-04-01"], "acceptance_datetime": ["2024-04-02T20:02:04.000Z"], "value": [1],
    })
    q = as_of(panel, "3", "Revenue", "2024-04-02T20:02:04Z")
    assert q.iloc[0]["time_precision"] == "ACCEPTANCE_TIMESTAMP"
    assert q.iloc[0]["known_at"] == pd.Timestamp("2024-04-02T20:02:04Z")
    assert as_of(panel, "3", "Revenue", "2024-04-02T20:02:03Z").empty
    # Same instant expressed with the US/Eastern UTC offset must behave identically.
    assert len(as_of(panel, "3", "Revenue", "2024-04-02T16:02:04-04:00")) == 1
    assert as_of(panel, "3", "Revenue", "2024-04-02T16:02:03-04:00").empty
    try:
        as_of(panel, "3", "Revenue", "2024-04-02T20:02:04")
    except ValueError as e:
        assert "EXPLICIT_TIMEZONE" in str(e)
    else:
        raise AssertionError("naive timestamp must fail")


def test_boundary_evidence_and_quality():
    import csv
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    rows = list(csv.DictReader((root / "data/research/p12_3_2_timezone_boundary_tests.csv").open(encoding="utf-8")))
    assert len(rows) == 10
    assert all(r["status"] == "PASS" for r in rows)
    q = {r["metric"]: r for r in csv.DictReader((root / "data/research/p12_3_2_precision_summary.csv").open(encoding="utf-8"))}
    assert q["filing_date_low_precision_rows"]["value"] == "118444"
    assert q["acceptance_timestamp_rows"]["value"] == "104360"
    doc = (root / "docs/research/P12_3_2_PIT_TIMEZONE_FINAL_AUDIT.md").read_text(encoding="utf-8")
    assert "P12_3_2_STATUS: READY_RESTRICTED" in doc
    assert "LOW_PRECISION_ROWS: 118444" in doc
