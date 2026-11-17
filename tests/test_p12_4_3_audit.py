import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"
P = DATA / "p12_4_3"


def _rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_horizon_exit_dates_and_holding_days():
    f = _rows(P / "p12_4_3_fundamental_panel.csv")
    assert len(f) == 2624
    assert all(r["entry_date"] for r in f)
    assert all(r["exit5_date"] for r in f)
    assert sum(1 for r in f if r["exit10_date"]) == 2620
    assert sum(1 for r in f if r["exit20_date"]) == 2617
    t = _rows(P / "p12_4_3_timezone_exit_tests.csv")
    assert len(t) == 5
    assert all(r["status"] == "PASS" for r in t)
    assert all(r["holding_days_5"] == "5" and r["holding_days_10"] == "10" and r["holding_days_20"] == "20" for r in t)


def test_period_boundaries_use_et_calendar():
    rows = _rows(P / "p12_4_3_period_boundary_tests.csv")
    assert all(r["status"] == "PASS" for r in rows)
    assert {r["et_disclosure_date"] for r in rows} >= {"2018-12-31", "2019-01-01", "2024-12-31"}


def test_off_by_one_changed_records():
    d = _rows(P / "p12_4_3_return_differences.csv")
    by = {r["horizon"]: r for r in d}
    assert by["5"]["changed_returns"] == "464"
    assert by["10"]["changed_returns"] == "464"
    assert by["20"]["changed_returns"] == "462"
    assert by["5"]["coverage_new"] == "2623"


def test_8k_d5_and_d20_have_separate_counts():
    e = _rows(P / "p12_4_3_8k_stats.csv")
    assert len(e) == 88
    assert all("n_d5_accessions" in r and "n_d20_accessions" in r for r in e)
    assert sum(1 for r in e if r["n_d5_accessions"] != r["n_d20_accessions"]) == 32


def test_2_02_clean_d20_is_not_signal():
    d = _rows(P / "p12_4_3_clean_window_stats.csv")
    x = [r for r in d if r["item"].startswith("2.02") and r["period"] == "validate" and r["sample"] == "clean_both" and r["horizon"] == "20"][0]
    assert float(x["mean"]) < 0.003
    assert float(x["p"]) > 0.10


def test_manifest_and_report():
    m = json.loads((P / "p12_4_3_run_manifest.json").read_text(encoding="utf-8"))
    assert m["bootstrap_reps"] == 500
    assert m["fundamental_accessions"] == 2624
    assert m["raw_data_committed"] is False
    doc = (ROOT / "docs/research/P12_4_3_FINAL_RETURN_HORIZON_AUDIT.md").read_text(encoding="utf-8")
    assert "P12_4_3_STATUS: DESCRIPTIVE_ONLY" in doc
    assert "FUNDAMENTAL_CHANGE: NO_SIGNAL" in doc
    assert "TRADABLE_ALPHA: NOT_CLAIMED" in doc
