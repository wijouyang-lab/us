import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"
P = DATA / "p12_4_1"


def _rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_protocol_and_samples():
    assert (ROOT / "docs/research/P12_4_1_PRE_REGISTERED_STUDY_PROTOCOL.md").exists()
    f = _rows(P / "p12_4_1_fundamental_panel.csv")
    e = _rows(P / "p12_4_1_8k_panel.csv")
    assert len(f) == 2624
    assert len({r["cik"] for r in f}) == 114
    assert len(e) == 11612
    assert len({r["accession"] for r in e}) == 11612


def test_metric_coverage_and_no_zero_fill():
    f = _rows(P / "p12_4_1_fundamental_panel.csv")
    for col in ("revenue_growth", "op_margin_change", "cash_conversion", "leverage_change", "shares_change"):
        assert sum(1 for r in f if r[col] != "") > 0
    # Missing values must remain blank, not zero.
    assert any(r["shares_change"] == "" for r in f)


def test_8k_window_coverage_and_categories():
    e = _rows(P / "p12_4_1_8k_panel.csv")
    assert sum(1 for r in e if r["d0_return"] != "") == 10945
    assert sum(1 for r in e if r["d1_return"] != "") == 10944
    assert sum(1 for r in e if r["d5_return"] != "") == 10941
    assert sum(1 for r in e if r["d10_return"] != "") == 10930
    assert sum(1 for r in e if r["d20_return"] != "") == 10869
    s = _rows(P / "p12_4_1_8k_stats.csv")
    assert len(s) == 88
    assert not any(r["item"] == "9.01" for r in s)


def test_5_02_overlap_sensitivity_removes_signal():
    rows = _rows(P / "p12_4_1_overlap_sensitivity.csv")
    x = {r["sample"]: r for r in rows if r["item"] == "5.02" and r["session"] == "AFTER_HOURS"}
    assert float(x["all"]["d20_excess_mean"]) > 0.005
    assert abs(float(x["clean_both"]["d20_excess_mean"])) < 0.001


def test_report_is_descriptive_only_and_manifest():
    doc = (ROOT / "docs/research/P12_4_1_PIT_FUNDAMENTAL_8K_EVENT_STUDY.md").read_text(encoding="utf-8")
    assert "P12_4_1_STATUS: DESCRIPTIVE_ONLY" in doc
    assert "FUNDAMENTAL_CHANGE: NO_SIGNAL" in doc
    assert "TRADABLE_ALPHA: NOT_CLAIMED" in doc
    assert "ALL 8 NO-GO" in doc
    m = json.loads((P / "p12_4_1_run_manifest.json").read_text(encoding="utf-8"))
    assert m["raw_data_committed"] is False
    assert m["fundamental_accessions"] == 2624
    assert m["8k_accessions"] == 11612
    assert not list(DATA.glob("*.parquet"))
