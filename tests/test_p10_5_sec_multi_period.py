import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p10_5_sec_multi_period"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_aapl_66_all_explained():
    rows = list(csv.DictReader((P / "aapl_all_accession_match.csv").open(encoding="utf-8")))
    assert len(rows) == 66
    assert all(r["dataset_status"] in {"DATASET_MATCHED","NOT_IN_DATASET","DATASET_NO_NUM_FACTS","ORIGINAL_FILING_NO_XBRL","UNRESOLVED"} for r in rows)
    assert sum(1 for r in rows if r["dataset_status"] == "DATASET_MATCHED") == 1
    assert len({r["dataset_quarter"] for r in rows}) == 64


def test_30_companies_120_parsed():
    rows = list(csv.DictReader((P / "cross_section_30_accession_coverage.csv").open(encoding="utf-8")))
    assert len(rows) == 120
    assert len({r["ticker"] for r in rows}) == 30
    assert all(r["status"] == "PARSED" for r in rows)
    assert all(r["cik"] for r in rows)


def test_field_coverage_and_run_manifest():
    rows = list(csv.DictReader((P / "cross_section_30_field_coverage.csv").open(encoding="utf-8")))
    assert len(rows) >= 30 * 15
    assert any(int(r["facts"]) > 0 for r in rows)
    m = load("run_manifest.json")
    assert len(m["git_commit_sha"]) == 40
    assert m["status"] == "PARTIAL_NOT_STRATEGY_READY"
    assert m["outputs"] and all(len(v["sha256"]) == 64 for v in m["outputs"].values())


def test_partial_not_strategy_ready_and_no_delisted_claim():
    s = load("p10_5_status.json")
    assert s["status"] == "P10_5_SEC_MULTI_PERIOD_PARTIAL"
    assert s["accessions_parsed"] == 120
    assert s["historical_delisted_companies"] == 0
    assert s["strategy_ready"] is False
    assert s["no_shadow"] is True
