import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p10_5_1_sec_remediation"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_aapl_66_have_final_status():
    rows = list(csv.DictReader((P / "aapl_all_accession_final_match.csv").open(encoding="utf-8")))
    assert len(rows) == 66
    assert all(r["dataset_status"] for r in rows)
    assert sum(1 for r in rows if r["dataset_status"] == "DATASET_MATCHED") == 1
    q = list(csv.DictReader((P / "aapl_quarterly_dataset_manifest.csv").open(encoding="utf-8")))
    assert len(q) == 64
    assert sum(1 for r in q if r["downloaded"] == "True") == 1


def test_parser_validation_sample_not_promoted():
    s = list(csv.DictReader((P / "historical_sample_selection.csv").open(encoding="utf-8")))
    assert len(s) == 30
    assert all(r["sample_role"] == "PARSER_VALIDATION_SAMPLE" for r in s)
    assert all(r["valid_historical_research_sample"] == "NO" for r in s)
    d = list(csv.DictReader((P / "delisted_company_evidence.csv").open(encoding="utf-8")))
    assert d == []


def test_asof_unit_test_returns_versions_not_retrospective():
    rows = list(csv.DictReader((P / "asof_query_test_results.csv").open(encoding="utf-8")))
    d = {r["query_date"]: r for r in rows}
    assert d["2021-01-01"]["value"] == "100"
    assert d["2023-01-01"]["value"] == "90"


def test_status_data_blocked_and_no_p10_6():
    s = load("p10_5_1_status.json")
    assert s["status"] == "P10_5_1_DATA_BLOCKED"
    assert s["p10_6_allowed"] is False
    assert s["valid_historical_sample"] is False
    assert s["delisted_companies"] == 0
    assert s["no_shadow"] is True
