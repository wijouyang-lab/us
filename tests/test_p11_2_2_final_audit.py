import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"
P = DATA / "p11_2_2"


def _rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_raw_and_excess_columns_are_separate():
    rows = _rows(P / "p11_2_2_factor_results.csv")
    assert len(rows) == 60
    required = {
        "mean_ic_raw", "mean_ic_excess", "top10_raw", "top10_excess_raw",
        "net_top10_raw", "net_top10_excess", "bh_q_raw", "bh_q_excess",
        "nonoverlap_ic_raw", "nonoverlap_n",
        "top10_incomplete_days", "quintile_incomplete_days",
    }
    assert required <= set(rows[0])
    assert all(float(r["return_coverage"]) > 0.95 for r in rows)


def test_no_positive_bh_significant_factor():
    rows = _rows(P / "p11_2_2_factor_results.csv")
    sig = [r for r in rows if float(r["bh_q_raw"]) < 0.05]
    assert len(sig) == 2
    assert all(r["factor"] == "mom5" and float(r["mean_ic_raw"]) < 0 for r in sig)
    assert max(float(r["mean_ic_raw"]) for r in rows) < 0.01


def test_missing_results_and_extreme_audit_are_explicit():
    rows = _rows(P / "p11_2_2_factor_results.csv")
    assert sum(int(r["top10_incomplete_days"]) for r in rows) > 0
    assert sum(int(r["quintile_incomplete_days"]) for r in rows) > 0
    assert sum(int(r["extreme_positive_obs"]) for r in rows) > 0
    audit = _rows(DATA / "p11_2_2_extreme_return_audit.csv")
    assert len(audit) == 8099
    assert all(r["status"] == "UNCONFIRMED_EXTREME" for r in audit)


def test_config_locks_primary_raw_returns_and_unfair_benchmark():
    c = json.loads((P / "p11_2_2_experiment_config.json").read_text(encoding="utf-8"))
    assert c["version"] == "2.2"
    assert c["benchmark_fair_comparison"] is False
    assert c["cost_model"] == "SIMPLIFIED_20BPS_ROUNDTRIP_NOT_IBKR"
    assert "Y not used" in c["sample_selection"]
    assert "portfolio returns raw" in c["winsorization"]


def test_report_is_no_go_and_preserves_prior_runs():
    doc = (ROOT / "docs/research/P11_2_2_FINAL_RESULTS_AUDIT.md").read_text(encoding="utf-8")
    assert "P11_2_2_STATUS: NO-GO" in doc
    assert "POSITIVE_TRADEABLE_ALPHA: NO" in doc
    assert "POSITIVE_BH_SIGNIFICANT_FACTORS: 0" in doc
    assert "BENCHMARK_FAIR: NO" in doc
    assert "ALL 8 NO-GO" in doc
    assert (DATA / "p11_2/p11_2_factor_results.csv").exists()
    assert (DATA / "p11_2_1/p11_2_1_factor_results.csv").exists()


def test_run_manifest_hashes_and_no_raw():
    m = json.loads((P / "p11_2_2_run_manifest.json").read_text(encoding="utf-8"))
    assert m["raw_data_committed"] is False
    assert m["ci_raw_replay"] is False
    assert len(m["inputs"]) == 3
    assert all(i["sha256"] for i in m["inputs"])
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))
