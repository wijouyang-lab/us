import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p10_1_pit_sources"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_source_audit_has_required_fields_and_statuses():
    rows = list(csv.DictReader((P / "source_audit.csv").open(encoding="utf-8")))
    assert len(rows) == 8
    assert all({"Source","Free access","Historical coverage","PIT availability","Publication timestamp","Revision history","Universe coverage","Missingness","Reproducibility","License","Status"} <= set(r) for r in rows)
    assert any(r["Status"] == "DATA_BLOCKED" for r in rows)


def test_no_source_is_strategy_ready():
    s = load("p10_1_status.json")
    assert s["status"] == "P10_1_PIT_DATA_PARTIAL"
    assert s["strategy_ready"] == []
    assert "SEC submissions metadata" in s["pit_verified"]


def test_sec_probe_has_acceptance_and_filed_dates():
    d = load("probe_results.json")["sources"]
    assert d["sec_submissions"]["http"] == 200
    assert d["sec_submissions"]["has_acceptance_timestamp"] is True
    assert d["sec_companyfacts"]["http"] == 200
    assert d["sec_companyfacts"]["facts"] > 1000
    assert d["sec_companyfacts"]["filed_min"] >= "2009-01-01"
    assert d["analyst_estimates"]["status"] == "DATA_BLOCKED"


def test_coverage_and_no_shadow():
    rows = list(csv.DictReader((P / "coverage_by_source.csv").open(encoding="utf-8")))
    assert any(r["coverage_status"] == "DATA_BLOCKED" for r in rows)
    assert (ROOT / "data/research/p9_2_benchmark_audit/p9_2_audit_status.json").exists()
    s = load("p10_1_status.json")
    assert "strategy" not in s or s.get("strategy_ready") == []
