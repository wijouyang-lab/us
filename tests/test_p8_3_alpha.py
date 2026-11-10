import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p8_3_valid_data_alpha"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_panel_and_label_coverage():
    m = load("valid_data_research_manifest.json")
    assert m["panel_rows"] > 300000
    assert 0.85 < m["valid_member_day_coverage"] < 0.95
    assert m["forward_label_coverage"] > 0.90
    assert (P / "valid_research_panel.parquet").exists()
    assert (P / "valid_data_coverage_by_year.csv").exists()
    assert (P / "valid_data_coverage_by_ticker.csv").exists()


def test_factor_registry_and_horizons():
    d = load("factor_definitions.json")
    assert len(d) == 33
    assert all({"window", "direction", "meaning"} <= set(v) for v in d.values())
    rows = list(csv.DictReader((P / "factor_ic_results.csv").open(encoding="utf-8")))
    assert len(rows) == 99
    assert {int(r["horizon"]) for r in rows} == {5, 10, 20}


def test_no_candidate_and_bh_fails():
    rows = list(csv.DictReader((P / "factor_ic_results.csv").open(encoding="utf-8")))
    assert all(float(r["bh_q"]) > 0.10 for r in rows)
    c = list(csv.DictReader((P / "strategy_candidates.csv").open(encoding="utf-8")))
    assert c == []
    s = load("p8_3_status.json")
    assert s["status"] == "P8_3_NO_GO"
    assert s["go_count"] == 0


def test_labels_are_not_zero_filled():
    rows = list(csv.DictReader((P / "valid_forward_label_coverage.csv").open(encoding="utf-8")))
    assert all(float(r["label_coverage"]) <= 1.0 for r in rows)
    assert any(float(r["label_coverage"]) < 1.0 for r in rows)
    assert (P / "valid_research_panel.parquet").exists()


def test_factor_ic_timeseries_and_correlation_exist():
    assert (P / "factor_ic_timeseries.csv").exists()
    assert (P / "factor_correlation.csv").exists()
    assert load("p8_3_status.json")["label_policy"].startswith("forward labels missing")


def test_snapshot_has_p8_3_not_shadow():
    s = json.loads((ROOT / "dashboard/data/invest_terminal_data.json").read_text(encoding="utf-8"))
    assert s["p8_3"]["status"] == "P8_3_NO_GO"
    assert s["p8_3"]["go_count"] == 0
    assert s["account"]["account_id"] == "PAPER-50000"
    assert "RESEARCH_SHADOW_P8" not in json.dumps(s)
