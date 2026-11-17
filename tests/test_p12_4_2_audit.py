import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"
P = DATA / "p12_4_2"


def _rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_timezone_entry_boundaries():
    from tools.research.p12.pit_query import _et_end_of_day
    assert _et_end_of_day("2025-03-09") == __import__("pandas").Timestamp("2025-03-10T03:59:59Z")
    assert _et_end_of_day("2025-11-02") == __import__("pandas").Timestamp("2025-11-03T04:59:59Z")
    rows = _rows(P / "p12_4_2_timezone_entry_tests.csv")
    assert len(rows) == 5
    assert all(r["status"] == "PASS" for r in rows)


def test_fundamental_panel_uses_entry_dates():
    f = _rows(P / "p12_4_2_fundamental_panel.csv")
    assert len(f) == 2624
    assert len({r["cik"] for r in f}) == 114
    assert all(r["entry_date"] and r["known_at"] for r in f)
    assert sum(1 for r in f if r["revenue_growth"] != "") > 0


def test_bootstrap_and_fdr_contract():
    m = json.loads((P / "p12_4_2_run_manifest.json").read_text(encoding="utf-8"))
    assert m["bootstrap_reps"] == 500
    assert m["bootstrap_seed"] == 20261117
    e = _rows(P / "p12_4_2_8k_stats.csv")
    assert len(e) == 88
    assert all(float(r["d5_p"]) > 0 for r in e if r["d5_p"])
    fs = _rows(P / "p12_4_2_fundamental_stats.csv")
    assert len(fs) == 45
    assert all(r["ic_bh_q"] for r in fs)


def test_2_02_clean_validation_does_not_confirm_signal():
    d = _rows(P / "p12_4_2_clean_window_stats.csv")
    x = [r for r in d if r["item"].startswith("2.02") and r["period"] == "validate" and r["sample"] == "clean_both" and r["horizon"] == "20"][0]
    assert float(x["mean"]) < 0.003
    assert float(x["p"]) > 0.10
    y = [r for r in d if r["item"].startswith("5.02") and r["period"] == "all" and r["sample"] == "clean_both" and r["horizon"] == "20"]
    assert all(abs(float(r["mean"])) < 0.003 for r in y)


def test_overlap_is_trading_window_not_calendar():
    rows = _rows(P / "p12_4_2_overlap_sensitivity.csv")
    x = {r["sample"]: r for r in rows if r["item"].startswith("5.02")}
    assert float(x["all"]["d20_excess_mean"]) > 0.005
    assert abs(float(x["clean_both"]["d20_excess_mean"])) < 0.001


def test_report_status():
    doc = (ROOT / "docs/research/P12_4_2_STATISTICAL_METHODOLOGY_AUDIT.md").read_text(encoding="utf-8")
    assert "P12_4_2_STATUS: DESCRIPTIVE_ONLY" in doc
    assert "FUNDAMENTAL_CHANGE: NO_SIGNAL" in doc
    assert "TRADABLE_ALPHA: NOT_CLAIMED" in doc
    assert "ALL 8 NO-GO" in doc
    assert not list(DATA.glob("*.parquet"))
