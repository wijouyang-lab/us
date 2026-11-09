import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p10_4_sec_dataset_integration"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_download_manifest_has_sha_and_size():
    rows = list(csv.DictReader((P / "sec_dataset_download_manifest.csv").open(encoding="utf-8")))
    assert len(rows) == 1
    r = rows[0]
    assert r["quarter"] == "2024q1"
    assert len(r["sha256"]) == 64
    assert int(r["bytes"]) > 100000000
    assert r["unzipped"] == "True"


def test_aapl_is_accession_linked_not_fuzzy():
    rows = list(csv.DictReader((P / "sec_dataset_accession_match.csv").open(encoding="utf-8")))
    assert len(rows) == 66
    matched = [r for r in rows if r["dataset_match"] == "MATCHED"]
    assert len(matched) == 1
    assert matched[0]["accession"] == "0000320193-24-000006"
    assert matched[0]["sub_adsh"] == "0000320193-24-000006"
    assert sum(1 for r in rows if r["dataset_match"] == "NOT_IN_DOWNLOADED_DATASET") == 65


def test_comparison_keeps_missing_and_diffs():
    rows = list(csv.DictReader((P / "aapl_sec_dataset_comparison.csv").open(encoding="utf-8")))
    assert len(rows) == 123
    statuses = {}
    for r in rows: statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    assert statuses.get("MATCHED_VALUE") == 121
    assert statuses.get("VALUE_DIFF", 0) == 0
    assert statuses.get("MISSING_IN_DATASET") == 2


def test_partial_not_strategy_ready():
    s = load("p10_4_status.json")
    assert s["status"] == "P10_4_SEC_DATASET_PARTIAL"
    assert s["strategy_ready"] is False
    cov = load("p10_4_coverage.json")
    assert cov["cross_section_parsed"] == 0
    assert cov["dataset_quarters"] == 1
    assert s["no_shadow"] is True
